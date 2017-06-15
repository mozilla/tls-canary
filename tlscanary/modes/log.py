# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import logging
import os
import sys

from basemode import BaseMode
import tlscanary.report as report
import tlscanary.runlog as rl


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
                           choices=["delete", "htmlreport", "json", "list"],
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
                                 "specifying the N latest logs, or any log handle. "
                                 "Can be specified repeatedly. (default: all)") % ",".join(cls.logging_modes),
                           action="append",
                           default=[])

        group.add_argument("-e", "--exclude",
                           help=("Exclude certain logs from log actions. Can be any of "
                                 "{complete,incomplete,incompatble}, any run mode of {%s}, an integer number "
                                 "specifying the N latest logs, or any log handle. "
                                 "Can be specified repeatedly. (default: None") % ",".join(cls.logging_modes),
                           action="append",
                           default=[])

        group = parser.add_argument_group("report generation")
        group.add_argument("-o", "--output",
                           help="Path to output directory for writing reports",
                           type=os.path.abspath,
                           action="store",
                           default=None)

    def __init__(self, args, module_dir, tmp_dir):
        super(LogMode, self).__init__(args, module_dir, tmp_dir)
        self.log_db = rl.RunLogDB(self.args)

        # Check arguments
        if len(self.args.include) == 0:
            logger.debug("No --include argument given, defaulting to `all`")
            self.args.include.append("all")

    def run(self):
        global logger

        log_handles = self.log_db.list()

        # Compile dict of all logs as {log handle => log object}
        all_logs = dict(zip(log_handles, map(self.log_db.read_log, log_handles)))

        # Filter log list according to includes and excludes
        log_list = self.compile_match_list(all_logs, self.args.include, self.args.exclude)
        if log_list is None:
            sys.exit(5)

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

            print json.dumps(log_data, indent=4, sort_keys=True)

        elif self.args.action == "jsonreport":
            if self.args.output is None:
                logger.critical("You must specify -o/--output for writing the JSON report")
                sys.exit(5)
            report.generate("json", log_list, self.args.output)

        elif self.args.action == "htmlreport":
            if self.args.output is None:
                logger.critical("You must specify -o/--output for writing the HTML report")
                sys.exit(5)
            report.generate("html", log_list, self.args.output)

        else:
            logger.critical("Report action `%s` not implemented" % self.args.action)
            sys.exit(5)

    def compile_match_list(self, all_logs, include, exclude):
        global logger

        # TODO: method needs testing
        # Compile list of included logs
        matching_logs = {}
        for arg in include:
            if arg == "all":
                matching_logs.update(all_logs)
            elif arg == "complete":
                for log_name in all_logs:
                    log = all_logs[log_name]
                    if log.has_finished():
                        matching_logs[log_name] = log
            elif arg == "incomplete":
                for log_name in all_logs:
                    log = all_logs[log_name]
                    if not log.has_finished():
                        matching_logs[log_name] = log
            elif arg == "incompatible":
                for log_name in all_logs:
                    log = all_logs[log_name]
                    if not log.is_compatible():
                        matching_logs[log_name] = log
            elif arg in self.logging_modes:
                for log_name in all_logs:
                    log = all_logs[log_name]
                    if log.get_meta()["mode"] == arg:
                        matching_logs[log_name] = log
            elif arg in all_logs:
                matching_logs[arg] = all_logs[arg]
            elif arg.isdigit():
                last_n = int(arg)
                for log_name in sorted(all_logs.keys())[-last_n:]:
                    log = all_logs[log_name]
                    matching_logs[log_name] = log
            else:
                logger.critical("Invalid -i/--include argument: `%s`" % arg)
                return None

        logger.debug("Included logs: %s" % sorted(matching_logs.keys()))

        # Throw away excluded logs
        for arg in exclude:
            if arg == "complete":
                for log_name in all_logs:
                    log = all_logs[log_name]
                    if log.has_finished() and log_name in matching_logs:
                        del(matching_logs[log_name])
            elif arg == "incomplete":
                for log_name in all_logs:
                    log = all_logs[log_name]
                    if not log.has_finished() and log_name in matching_logs:
                        del(matching_logs[log_name])
            elif arg == "incompatible":
                for log_name in all_logs:
                    log = all_logs[log_name]
                    if not log.is_compatible() and log_name in matching_logs:
                        del (matching_logs[log_name])
            elif arg in self.logging_modes:
                for log_name in all_logs:
                    log = all_logs[log_name]
                    if log.get_meta()["mode"] == arg and log_name in matching_logs:
                        del(matching_logs[log_name])
            elif arg in all_logs:
                if arg in matching_logs:
                    del(matching_logs[arg])
            elif arg.isdigit():
                last_n = int(arg)
                for log_name in sorted(all_logs.keys())[-last_n:]:
                    if log_name in matching_logs:
                        del (matching_logs[log_name])
            else:
                logger.critical("Invalid -e/--exclude argument: `%s`" % arg)
                return None

        logger.debug("Included logs after exclusion: %s" % sorted(matching_logs.keys()))
        return matching_logs

    @staticmethod
    def print_log_list(log_list):
        for log_name in sorted(log_list.keys()):
            log = log_list[log_name]
            meta = log.get_meta()
            mode = meta["mode"] if "mode" in meta else "unknown"
            incomplete_marker = "" if log.has_finished() else "(*)"
            if not log.is_compatible():
                print "%s\t\t\t\t\t\tINCOMPATIBLE LOG FORMAT" % log_name
            elif mode == "regression" or mode == "performance":
                print "%s%s\tlines=%-6d\tmode=%-12s\tFx %s %s / %s vs. Fx %s %s / %s" % (
                    log_name,
                    incomplete_marker,
                    len(log),
                    mode,
                    meta["test_metadata"]["app_version"],
                    meta["test_metadata"]["branch"].capitalize(),
                    meta["test_metadata"]["nss_version"],
                    meta["base_metadata"]["app_version"],
                    meta["base_metadata"]["branch"].capitalize(),
                    meta["base_metadata"]["nss_version"])
            elif mode == "scan":
                print "%s%s\tlines=%-6d\tmode=%-12s\tFx %s %s / %s" % (
                    log_name,
                    incomplete_marker,
                    len(log),
                    mode,
                    meta["test_metadata"]["app_version"],
                    meta["test_metadata"]["branch"].capitalize(),
                    meta["test_metadata"]["nss_version"])
            else:
                print "%s%s\t lines=%-6d\tmode=%-12s" % (
                    log_name,
                    incomplete_marker,
                    meta["log_lines"],
                    mode)
