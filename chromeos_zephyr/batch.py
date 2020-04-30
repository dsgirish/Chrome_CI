# -*- coding: utf-8 -*
#!/usr/bin/env python
'''
The purpose of this script is to generate and execute the commands of
junit_converter.py and zephyr_zapi.py.
It can be used when multiple test cycle updates are required for one project.
'''
import os
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import argparse
import glob
import subprocess
import time
import logging

import conf

def main():
    start_time = time.time()
    args = ParseArgs()
    conf.ConfigLogging(args.debug, args.verbose)
    ExecuteScripts(args)
    end_time = time.time()
    logging.info("Execution completes. Runtime: %s seconds" % (round(end_time - start_time)))

def ParseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", help="Debug mode", action="store_true")
    parser.add_argument("-v", "--verbose", help="Verbose mode", action="store_true")
    parser.add_argument("-c", "--config", help="Project config file", default = "project_config.json")
    parser.add_argument("-p", "--profile", help="Choose config profile for processing")    
    parser.add_argument("--junitScript", "--junitscript", "-j", help="The file path to junit_converter.py", default = "junit_converter.py")
    parser.add_argument("--zephyrScript", "--zephyrscript", "-z", help="The file path to zephyr_zapi.py", default = "zephyr_zapi.py")
    parser.add_argument("--dryRun", "--dryrun", action='store_true', help="Only generate the commands without execution")
    parser.add_argument("--cycleSuffix", "--cyclesuffix", help="Suffix of test cycle names, i.e. work week numbers like 2019ww02", default = "")
    parser.add_argument("log", help="The folder path to the test logs")
    parser.add_argument("output", help="The folder path to the junit output folder")
    args = parser.parse_args()
    return args

def ExecuteScripts(args):
    mode = ''
    if args.verbose:
        mode = " -v "
    if args.debug:
        mode = " -d "
    configPath = ConvertToAbspath(args.config)
    junitScript = ConvertToAbspath(args.junitScript)
    zephyrScript = ConvertToAbspath(args.zephyrScript)
    logPath = ConvertToAbspath(args.log)
    outputPath = ConvertToAbspath(args.output)

    os.chdir(logPath)
    for cycle in glob.glob('*'):
        junitFile = "\"" + os.path.join(outputPath, cycle + "_output.xml") + "\""
        junitCommand = "Python \"" + junitScript + "\"" + mode + \
            " --log \"" + os.path.abspath(cycle) + "\"" + \
            " --config \"" + configPath + "\"" + \
            " --profile " + args.profile + \
            " -o " + junitFile
        CallCommand(args.dryRun, junitCommand)

        zapiCommand = "Python \"" + zephyrScript + "\"" + mode + \
            " --config \"" + configPath + "\"" + \
            " --profile " + args.profile + \
            " execute " + \
            " -f " + junitFile
        zql = " --cycleName \"" + cycle + args.cycleSuffix + "\""
        CallCommand(args.dryRun, zapiCommand, zql)

def CallCommand(dryRun, *subCommands):
    """
    combine the pieces of sub commands and execute the command
    :params dryRun: True is to display the command, while False is to execute the command
    :params *subCommands: the pieces of sub commands 
    """
    command = ''
    for subCommand in subCommands:
        command += subCommand
    logging.info("zapi command: \n%s" % (command))
    if not dryRun:
        subprocess.call(command, shell=True)

def ConvertToAbspath(path):
    if not os.path.exists(path):
        logging.error("Path %s doesn't exist, please verify." % (path))
        sys.exit(1)
    if os.path.isabs(path):
        return path
    else:
        return os.path.abspath(path)

if __name__ == '__main__':
    main()
