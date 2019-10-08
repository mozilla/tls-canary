# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import logging
import os
import sys

from .basemode import BaseMode
import tlscanary.report as report
import tlscanary.runlog as rl
import tlscanary.tools.tags_db as tdb

logger = logging.getLogger(__name__)


class LogMode(BaseMode):
    """
    Mode to access run logs and generate reports
    """

    name = "log"
    help = "Query and maintain the run log database and create reports"
    logging_modes = ["performance", "regression", "scan"]

    @classmethod
    def setup_args(cls, parser):

        group = parser.add_argument_group("log actions")

        group.add_argument("-a", "--action",
                           help="Action to perform (default: list)",
                           choices=["delete", "webreport", "json", "list",
                                    "addtag", "rmtag", "droptag"],
                           action="store",
                           default="list")

        group.add_argument("--really",
                           help="Sanity flag required by dangerous actions like `delete`",
                           action="store_true")

        group = parser.add_argument_group("log selection")
        # Breaking alphabetical ordering, because logically `include` happens before `exclude`
        group.add_argument("-i", "--include",
                           help=("Include certain logs in log actions. Can be any of "
                                 "{all,complete,incomplete,incompatible}, any run mode of {%s}, an integer number "
                                 "specifying the N latest logs, or any log handle, or any tag. "
                                 "Can be specified repeatedly. (default: all)") % ",".join(cls.logging_modes),
                           action="append",
                           default=[])

        group.add_argument("-e", "--exclude",
                           help=("Exclude certain logs from log actions. Can be any of "
                                 "{complete,incomplete,incompatible}, any run mode of {%s}, an integer number "
                                 "specifying the N latest logs, or any log handle, or any tag. "
                                 "Can be specified repeatedly. (default: None") % ",".join(cls.logging_modes),
                           action="append",
                           default=[])

        group = parser.add_argument_group("report generation")
        group.add_argument("-o", "--output",
                           help="Path to output directory for writing reports",
                           type=os.path.abspath,
                           action="store",
                           default=None)

        group = parser.add_argument_group("tag operation")
        group.add_argument("-t", "--tag",
                           help="Specify a tag name for tag-related actions",
                           type=str,
                           default=None)

    def __init__(self, args, module_dir, tmp_dir):
        super(LogMode, self).__init__(args, module_dir, tmp_dir)
        self.log_db = rl.RunLogDB(self.args)
        self.tag_db = tdb.TagsDB(self.args)
        self.tag_db.remove_dangling(self.log_db.list(), save=True)

        # Check arguments
        if len(self.args.include) == 0:
            logger.debug("No --include argument given, defaulting to `all`")
            self.args.include.append("all")

    def run(self):
        global logger

        log_handles = self.log_db.list()

        # Compile dict of all logs as {log handle => log object}
        all_logs = dict(list(zip(log_handles, list(map(self.log_db.read_log, log_handles)))))

        # Add standard tags
        self.add_standard_tags(all_logs)

        # Filter log list according to includes and excludes
        log_list = self.compile_match_list(all_logs, self.args.include, self.args.exclude)
        if log_list is None:
            logger.warning("Include/exclude selection yielded no logs")
            sys.exit(0)

        # See what to do with those logs
        if self.args.action is None or self.args.action == "list":
            self.print_log_list(log_list)

        elif self.args.action == "delete":
            if not self.args.really:
                for log_name in sorted(log_list.keys()):
                    logger.info("Would delete log `%s`" % log_name)
                logger.critical("Is this what you --really want?")
                sys.exit(0)
            else:
                for log_name in sorted(log_list.keys()):
                    logger.info("Deleting log `%s`" % log_name)
                    log_list[log_name].delete()

        elif self.args.action == "json":
            log_data = []
            for log_name in log_list:
                log = self.log_db.read_log(log_name)
                meta = log.get_meta()
                if not meta["run_completed"]:
                    logger.warning("Skipping incomplete log `%s`" % log_name)
                    continue
                log_data.append({"meta": log.get_meta(), "data": [line for line in log]})

            print(json.dumps(log_data, indent=4, sort_keys=True))

        elif self.args.action == "jsonreport":
            if self.args.output is None:
                logger.critical("You must specify -o/--output for writing the JSON report")
                sys.exit(5)
            report.generate("json", log_list, self.args.output)

        elif self.args.action == "webreport":
            if self.args.output is None:
                logger.critical("You must specify -o/--output for writing the HTML report")
                sys.exit(5)
            report.generate("web", log_list, self.args.output)

        elif self.args.action == "addtag":
            if not self.tag_db.is_valid_tag(self.args.tag):
                logger.critical("Tag action requires valid --tag")
                sys.exit(5)
            for log_name in log_list:
                logger.debug("Adding tag `%s` to log `%s`" % (self.args.tag, log_name))
                self.tag_db.add(self.args.tag, log_name, save=False)
            self.tag_db.save()

        elif self.args.action == "rmtag":
            if not self.tag_db.is_valid_tag(self.args.tag):
                logger.critical("Tag action requires valid --tag")
                sys.exit(5)
            for log_name in log_list:
                logger.debug("Removing tag `%s` from log `%s`" % (self.args.tag, log_name))
                self.tag_db.remove(self.args.tag, log_name, save=False)
            self.tag_db.save()

        elif self.args.action == "droptag":
            if not self.tag_db.is_valid_tag(self.args.tag):
                logger.critical("Tag action requires valid --tag")
                sys.exit(5)
            if not self.args.really:
                for log_name in sorted(list(self.tag_db.tag_to_handles(self.args.tag))):
                    logger.info("Would remove `%s` tag from log `%s`" % (self.args.tag, log_name))
                logger.critical("Is this what you --really want?")
                sys.exit(0)
            logger.debug("Removing tag `%s` from all logs that have it" % self.args.tag)
            self.tag_db.drop(self.args.tag)

        else:
            logger.critical("Report action `%s` not implemented" % self.args.action)
            sys.exit(5)

    def add_standard_tags(self, logs: dict, save=True):
        t = self.tag_db
        t.drop("complete", save=False)
        t.drop("incomplete", save=False)
        t.drop("incompatible", save=False)

        for log_name, log in logs.items():
            if not log.is_compatible():
                t.add("incompatible", log_name, save=False)
            else:
                t.add(log.get_meta()["mode"], log_name, save=False)
                t.add("complete" if log.has_finished() else "incomplete", log_name, save=False)
        if save:
            t.save()

    def compile_match_list(self, all_logs, include, exclude):
        global logger

        if include is None or len(include) == 0:
            include = ["all"]

        if exclude is None:
            exclude = []

        # TODO: method needs testing
        # Compile list of included logs
        matching_logs = {}
        for arg in include:
            if arg == "all":
                matching_logs.update(all_logs)
            elif arg in all_logs:
                matching_logs[arg] = all_logs[arg]
            elif arg.isdigit():
                last_n = int(arg)
                for log_name in sorted(all_logs.keys())[-last_n:]:
                    log = all_logs[log_name]
                    matching_logs[log_name] = log
            elif self.tag_db.is_valid_tag(arg) and len(self.tag_db[arg]) > 0:
                for log_name in self.tag_db[arg]:
                    log = all_logs[log_name]
                    matching_logs[log_name] = log
            else:
                logger.warning("No match for -i/--include argument: `%s`" % arg)
                return None

        logger.debug("Included logs: %s" % sorted(matching_logs.keys()))

        # Throw away excluded logs
        for arg in exclude:
            if arg in all_logs:
                if arg in matching_logs:
                    del(matching_logs[arg])
            elif arg.isdigit():
                last_n = int(arg)
                for log_name in sorted(all_logs.keys())[-last_n:]:
                    if log_name in matching_logs:
                        del (matching_logs[log_name])
            elif self.tag_db.is_valid_tag(arg) and len(self.tag_db[arg]) > 0:
                for log_name in self.tag_db[arg]:
                    log = all_logs[log_name]
                    matching_logs[log_name] = log
            else:
                logger.debug("No match for -e/--exclude argument: `%s`" % arg)

        logger.debug("Included logs after exclusion: %s" % sorted(matching_logs.keys()))
        return matching_logs

    def print_log_list(self, log_list):
        for log_name in sorted(log_list.keys()):
            log = log_list[log_name]
            meta = log.get_meta()
            tags = self.tag_db.handle_to_tags(log_name)
            mode = meta["mode"] if "mode" in meta else "unknown"
            if not log.is_compatible():
                print("%s\t            \ttags=%-39s\tINCOMPATIBLE LOG FORMAT" % (log_name, "+".join(tags)))
            elif mode == "regression" or mode == "performance":
                size = os.path.getsize((log.part("log.bz2")))
                if size > 100*1024*1024:
                    logger.warning("Log `%s` contains %.1f MBytes of data. counting may take a while"
                                   % (log.handle, size/1024.0/10124.0))
                print("%s\tlines=%-6d\ttags=%-39s\tFx %s %s / %s vs. Fx %s %s / %s" % (
                    log_name,
                    len(log),
                    "+".join(tags),
                    meta["test_metadata"]["app_version"],
                    meta["test_metadata"]["branch"].capitalize(),
                    meta["test_metadata"]["nss_version"],
                    meta["base_metadata"]["app_version"],
                    meta["base_metadata"]["branch"].capitalize(),
                    meta["base_metadata"]["nss_version"]))
            elif mode == "scan":
                size = os.path.getsize((log.part("log.bz2")))
                if size > 100*1024*1024:
                    logger.warning("Log `%s` contains %.1f MBytes of data. Counting may take a while"
                                   % (log.handle, size/1024.0/1024.0))
                print("%s\tlines=%-6d\ttags=%-39s\tFx %s %s / %s" % (
                    log_name,
                    len(log),
                    "+".join(tags),
                    meta["test_metadata"]["app_version"],
                    meta["test_metadata"]["branch"].capitalize(),
                    meta["test_metadata"]["nss_version"]))
            else:
                print("%s\tlines=%-6d\ttags=%-39s" % (
                    log_name,
                    len(log),
                    "+".join(tags)))
