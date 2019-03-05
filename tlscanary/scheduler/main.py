#!/usr/bin/env python3
# -*- coding: utf8 -*-

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import coloredlogs
import json
import logging
from multiprocessing import Pool
import os
import schedule
from shutil import which
from subprocess import check_output, CalledProcessError, run
import sys
import time

# Load Matplotlib in "headless" mode to prevent carnage
# CAVE: Every matplotlib property used by this code must be explicitly imported in the dummy
from .matplotlib_agg import matplotlib
from matplotlib.dates import datestr2num
import matplotlib.pyplot as plt

# Initialize coloredlogs
logging.Formatter.converter = time.gmtime
logger = logging.getLogger(__name__)
coloredlogs.DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s"
coloredlogs.install(level="INFO")


def list_logs(tlscanary: str, tag: str = "all") -> list:
    cmd = [tlscanary, "log", "-i", tag, "-e", "incomplete", "-e", "incompatible"]
    logger.info("Running `%s`" % " ".join(cmd))
    log_output = check_output(cmd).decode("utf-8").split("\n")[:-1]

    # Log reference is in leftmost column of output
    return list(sorted(map(lambda line: line.split("\t")[0], log_output)))


def get_log(tlscanary: str, ref: str) -> dict:
    cmd = [tlscanary, "log", "-a", "json", "-i", str(ref)]

    # Retries are necessary as EC2 instances are running into spurious BrokenPipe errors
    # when spawning tlscanary subprocesses, likely due to memory underruns.
    retries = 5
    out = None
    while out is None and retries > 0:
        try:
            logger.debug("Running `%s`" % " ".join(cmd))
            out = check_output(cmd).decode("utf-8")
        except CalledProcessError:
            logger.warning("Retrying failed command `%s`" % " ".join(cmd))
            retries -= 1

    if out is None:
        logger.critical("Giving up on retrying command `%s`" % " ".join(cmd))
        raise Exception("Number of retries exceeded")

    return json.loads(out)


def process_log(log: dict, mode: str):

    if len(log) == 0:
        raise Exception("Empty log")

    set_size = int(log[0]["meta"]["sources_size"])
    timestamp = datestr2num(log[0]["meta"]["run_finish_time"])

    # Extract filtered list of affected hosts and ranks
    carnage = []
    for log_data in log[0]["data"]:
        if mode == "symantec":
            # Old way of counting stopped working once NSS changes removed short error message
            # if "short_error_message" in l["response"]["result"]["info"]:
            #     sm = l["response"]["result"]["info"]["short_error_message"]
            #     if sm == "SEC_ERROR_UNKNOWN_ISSUER" or sm == "MOZILLA_PKIX_ERROR_ADDITIONAL_POLICY_CONSTRAINT_FAILED":
            #         errors += 1
            # New way of counting is solely filtering by ssl status code
            status = log_data["response"]["result"]["info"]["status"]
            if status == 2153398259 or status == 2153390067:
                carnage.append((int(log_data["rank"]), log_data["host"]))
        elif mode == "tlsdeprecation":
            status = log_data["response"]["result"]["info"]["short_error_message"]
            if status == "SSL_ERROR_UNSUPPORTED_VERSION":
                carnage.append((int(log_data["rank"]), log_data["host"]))
        else:
            raise Exception("Unknown log processing mode: %s" % mode)

    carnage = list(sorted(carnage))

    # Count numbers for each subset
    counts = {}
    for key in (100, 1000, 10000, 100000, 1000000):
        counts[str(key)] = 0
    for rank, _ in carnage:
        for key in (100, 1000, 10000, 100000, 1000000):
            if rank <= key:
                counts[str(key)] += 1

    return timestamp, set_size, carnage, counts


class SymantecJob(object):

    def __init__(self, tlscanary_binary: str, output_path: str):
        self.log_tag = "symantec"
        self.tlscanary_binary = tlscanary_binary
        self.output_path = output_path
        self.plot_file = os.path.join(output_path, "symantec-plot.svg")
        self.carnage_file = os.path.join(output_path, "symantec-carnage.txt")

    def run(self):
        logger.info("Starting Symantec scan")
        self.scan()
        logger.info("Processing Symantec logs")
        self.update_plot()
        logger.info("Completed Symantec job")

    def update_plot(self):
        data = self.process_logs()
        logger.info("Writing Symantec plot to `%s`" % self.plot_file)
        self.generate_plot(data)
        logger.info("Writing carnage to `%s`" % self.carnage_file)
        self.write_latest_carnage()

    def scan(self):
        cmd = [self.tlscanary_binary,
               "regression", "-r",
               "-t", "beta",
               "-p1", "security.pki.distrust_ca_policy;2",
               "-b", "beta",
               "-p2", "security.pki.distrust_ca_policy;0"
               ]
        logger.info("Running `%s`" % " ".join(cmd))
        run(cmd, check=True)
        cmd = [self.tlscanary_binary, "log", "-i", "1", "-a", "addtag", "-t", self.log_tag]
        logger.info("Running `%s`" % " ".join(cmd))
        run(cmd, check=True)

    def process_log(self, ref: str):
        timestamp, set_size, _, counts = process_log(get_log(self.tlscanary_binary, ref), mode=self.log_tag)
        return timestamp, set_size, counts

    def process_logs(self) -> dict:
        # with open("/home/ubuntu/http/broken-%s.csv" % key, "w") as f:
        #     f.writelines(["%d,%s\n" % x for x in sorted(carnage)])
        data = {}
        p = Pool()
        work_list = list_logs(self.tlscanary_binary, tag=self.log_tag)
        results = p.imap_unordered(self.process_log, work_list)

        # Add static data compiled by matt
        data["1000000"] = {
                "timestamps": [
                    datestr2num("2018-05-22"),
                    datestr2num("2018-06-26"),
                    datestr2num("2018-07-17"),
                    datestr2num("2018-08-15")
                ],
                "values": [
                    # original set_size was 496833 hosts
                    100.0 * 35066 / 1000000,
                    100.0 * 27102 / 1000000,
                    100.0 * 23197 / 1000000,
                    100.0 * 17833 / 1000000
                ]
        }

        for timestamp, _, counts in sorted(results):
            for tier in counts.keys():
                # if tier == "100000":
                #     continue
                value = 100.0 * counts[tier] / int(tier)
                if tier not in data:
                    data[tier] = {"timestamps": [timestamp], "values": [value]}
                else:
                    data[tier]["timestamps"].append(timestamp)
                    data[tier]["values"].append(value)

        return data

    def write_latest_carnage(self):
        try:
            ref = list_logs(self.tlscanary_binary, tag=self.log_tag)[-1]
        except IndexError:
            logger.warning("Nothing logged for `%s`" % self.log_tag)
            return

        _, _, data, _ = process_log(get_log(self.tlscanary_binary, ref), mode=self.log_tag)

        with open(self.carnage_file, "w") as f:
            f.writelines(["rank,host\n"])
            f.writelines(["%s,%s\n" % (rank, host) for rank, host in sorted(data)])

    def generate_plot(self, data: dict):
        # Tips about matplotlib styling:
        # http://messymind.net/making-matplotlib-look-like-ggplot/

        fig, ax = plt.subplots(figsize=(9, 5))
        fig.suptitle("Percentage of Symantec regressions", fontsize=14)

        # https://matplotlib.org/users/colormaps.html
        cmap = plt.cm.get_cmap('tab10', 10)

        for i, k in enumerate(sorted(data.keys())):
            ax.plot_date(data[k]["timestamps"], data[k]["values"],
                         color=cmap(i), linestyle='-', markersize=0, label="Top %s" % k)

        ax.grid(True, 'major', color='1.0', linestyle='-', linewidth=0.7)
        ax.grid(True, 'minor', color='0.95', linestyle='-', linewidth=0.5)

        # Remove outer box
        for child in ax.get_children():
            if isinstance(child, matplotlib.spines.Spine):
                child.set_alpha(0)

        ax.patch.set_facecolor('0.92')
        ax.set_axisbelow(True)
        ax.set_ylim(bottom=0)

        ax.legend(loc='upper left')
        ax.legend_.get_frame().set_linewidth(0)
        ax.legend_.get_frame().set_alpha(0.5)

        # ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
        plt.gcf().autofmt_xdate()

        plt.savefig(self.plot_file)
        # plt.show()
        plt.close()


class TLSDeprecationJob(object):

    def __init__(self, tlscanary_binary, output_path: str):
        self.log_tag = "tlsdeprecation"
        self.tlscanary_binary = tlscanary_binary
        self.output_path = output_path
        self.plot_file = os.path.join(output_path, "tlsdeprecation-plot.svg")
        self.carnage_file = os.path.join(output_path, "tlsdeprecation-carnage.txt")

    def run(self):
        logger.info("Starting TLS Deprecation scan")
        self.scan()
        logger.info("Processing TLS Deprecation logs")
        self.update_plot()
        logger.info("Completed TLS Deprecation job")

    def update_plot(self):
        data = self.process_logs()
        logger.info("Writing TLS Deprecation plot to `%s`" % self.plot_file)
        self.generate_plot(data)
        logger.info("Writing carnage to `%s`" % self.carnage_file)
        self.write_latest_carnage()

    def scan(self):
        cmd = [self.tlscanary_binary,
               "regression", "-r",
               "-t", "beta",
               "-p1", "security.tls.version.min;3",
               "-b", "beta",
               "-p2", "security.tls.version.min;1"
               ]
        logger.info("Running `%s`" % " ".join(cmd))
        run(cmd, check=True)
        cmd = [self.tlscanary_binary, "log", "-i", "1", "-a", "addtag", "-t", self.log_tag]
        logger.info("Running `%s`" % " ".join(cmd))
        run(cmd, check=True)

    def process_log(self, ref: str):
        timestamp, set_size, _, counts = process_log(get_log(self.tlscanary_binary, ref), mode=self.log_tag)
        return timestamp, set_size, counts

    def process_logs(self) -> dict:
        # with open("/home/ubuntu/http/broken-%s.csv" % key, "w") as f:
        #     f.writelines(["%d,%s\n" % x for x in sorted(carnage)])
        data = {}
        p = Pool()
        work_list = list_logs(self.tlscanary_binary, tag=self.log_tag)
        results = p.imap_unordered(self.process_log, work_list)

        for timestamp, _, counts in sorted(results):
            for tier in counts.keys():
                # if tier == "100000":
                #     continue
                value = 100.0 * counts[tier] / int(tier)
                if tier not in data:
                    data[tier] = {"timestamps": [timestamp], "values": [value]}
                else:
                    data[tier]["timestamps"].append(timestamp)
                    data[tier]["values"].append(value)

        return data

    def write_latest_carnage(self):
        try:
            ref = list_logs(self.tlscanary_binary, tag=self.log_tag)[-1]
        except IndexError:
            logger.warning("Nothing logged for `%s`" % self.log_tag)
            return

        _, _, data, _ = process_log(get_log(self.tlscanary_binary, ref), mode=self.log_tag)

        with open(self.carnage_file, "w") as f:
            f.writelines(["rank,host\n"])
            f.writelines(["%s,%s\n" % (rank, host) for rank, host in sorted(data)])

    def generate_plot(self, data: dict):
        # Tips about matplotlib styling:
        # http://messymind.net/making-matplotlib-look-like-ggplot/

        fig, ax = plt.subplots(figsize=(9, 5))
        fig.suptitle("TLS 1.1 Deprecation Regressions (%)", fontsize=14)

        # https://matplotlib.org/users/colormaps.html
        cmap = plt.cm.get_cmap('tab10', 10)

        for i, k in enumerate(sorted(data.keys())):
            ax.plot_date(data[k]["timestamps"], data[k]["values"],
                         color=cmap(i), linestyle='-', markersize=0, label="Top %s" % k)

        ax.grid(True, 'major', color='1.0', linestyle='-', linewidth=0.7)
        ax.grid(True, 'minor', color='0.95', linestyle='-', linewidth=0.5)

        # Remove outer box
        for child in ax.get_children():
            if isinstance(child, matplotlib.spines.Spine):
                child.set_alpha(0)

        ax.patch.set_facecolor('0.92')
        ax.set_axisbelow(True)
        ax.set_ylim(bottom=0)

        ax.legend(loc='upper left')
        ax.legend_.get_frame().set_linewidth(0)
        ax.legend_.get_frame().set_alpha(0.5)

        # ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
        plt.gcf().autofmt_xdate()

        logger.info("Writing TLS Deprecation plot to `%s`" % self.plot_file)
        plt.savefig(self.plot_file)
        # plt.show()
        plt.close()


class SrcUpdateJob(object):

    def __init__(self, tlscanary_binary):
        self.tlscanary_binary = tlscanary_binary

    def run(self):
        logger.info("Updating sources")
        # Setting distrust policy to 0 as long as we need to capture hosts for Symantec regressions
        cmd = [self.tlscanary_binary, "srcupdate", "-p", "security.pki.distrust_ca_policy;0"]
        logger.info("Running `%s`" % " ".join(cmd))
        run(cmd, check=True)
        logger.info("Completed source update job")


class Scheduler(object):

    @staticmethod
    def log_alive():
        logger.info("Scheduler is alive")

    @staticmethod
    def run(output_directory: str) -> int:
        tlscanary_binary = "tlscanary"

        output_directory = os.path.abspath(output_directory)
        logger.info("Output directory is `%s`" % output_directory)

        symantec = SymantecJob(tlscanary_binary, os.path.join(output_directory))
        tlsdeprecation = TLSDeprecationJob(tlscanary_binary, os.path.join(output_directory))
        srcupdate = SrcUpdateJob(tlscanary_binary)

        # ####################################################################
        # Here's the the actual schedule #####################################
        # ####################################################################
        schedule.every(60).minutes.do(Scheduler.log_alive)
        schedule.every().monday.at("00:00").do(symantec.run)
        schedule.every().wednesday.at("00:00").do(tlsdeprecation.run)
        schedule.every().saturday.at("00:00").do(srcupdate.run)

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)

        except KeyboardInterrupt:
            logger.critical("\nUser interrupt. Quitting...")
            return 10

    @staticmethod
    def update_plots(output_directory: str) -> int:
        tlscanary_binary = "tlscanary"
        symantec = SymantecJob(tlscanary_binary, output_directory)
        tlsdeprecation = TLSDeprecationJob(tlscanary_binary, output_directory)
        symantec.update_plot()
        tlsdeprecation.update_plot()
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scheduler for TLS Canary scan jobs")
    parser.add_argument("--debug",
                        help="enable debug-level logging",
                        action="store_true")
    parser.add_argument("--update",
                        help="just update the plots and exit",
                        action="store_true")
    parser.add_argument("path",
                        help="path to output directory for jobs",
                        metavar="output path",
                        type=str)
    args = parser.parse_args()

    if args.debug:
        coloredlogs.install(level="DEBUG")

    logger.debug("Parsed args: %s" % args)

    if not os.path.isdir(args.path):
        logger.critical("output path is not a valid directory")
        return 10

    if not which("tlscanary"):
        logger.critical("`tlscanary` binary is not in path. Did you activate the Python env?")
        return 11

    if args.update:
        return Scheduler.update_plots(args.path)

    return Scheduler.run(args.path)


if __name__ == "__main__":
    sys.exit(main())
