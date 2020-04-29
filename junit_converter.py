# -*- coding: utf-8 -*
#!/usr/bin/env python
'''
The purpose of this script is to convert the output of the test execution
engine’s log files into JUnit files. These files can then be uploaded to Zephyr
 with the assistance of the zephyr_zapi.py script.
The general flow of the script is the following:
1.Find the log files (You will need to edit your project’s log file pattern in
your project config file)
2.Parse through the log files looking for test cases and results (You will
also need to edit the regular expression to find the test cases in your project
config file)
3.The JUnit file is then be generated.
'''
import os
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import platform
import argparse
import re
import glob
import shutil
import subprocess
import datetime
import logging
from collections import defaultdict
from junit_xml import TestSuite, TestCase

import conf

def main():
    args = ParseArgs()
    projectConfig = conf.GetProjectConfig(args.config)
    conf.ConfigLogging(args.debug, args.verbose)
    args = conf.ApplyProjectConfigToArgs(args, projectConfig)

    #Default test status patterns, can be customized and overwritten in your project config file.
    passPattern = "(PASSED|passing|Pass|Success)"
    failPattern = "(Failed|failing|Failure|fail)"
    blockPattern = "(Blocked|block)"
    skipPattern = "(Skipped|skipping|skip|no run|not executed|n/a)"
    (logFilePattern, testCasePattern, passPattern, failPattern, blockPattern, skipPattern) = conf.GetConfigPattern(args.profile, projectConfig)
    VerifyResults(args.profile, projectConfig, logFilePattern, testCasePattern, passPattern, failPattern, blockPattern, skipPattern)

    junit_test_suites = ProcessLogFile(args.log, args.format, args.encoding, logFilePattern, testCasePattern, passPattern, failPattern, blockPattern, skipPattern)
    WriteTestResultsToJunit(args.outFile, junit_test_suites)

def ParseArgs():
    '''
    parse the arguments
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", help="Debug mode", action="store_true")
    parser.add_argument("-v", "--verbose", help="Verbose mode", action="store_true")
    parser.add_argument("-c", "--config", help="Project config file, project_config.json by default", default = 'project_config.json')
    parser.add_argument("-p", "--profile", required=True, help="Choose the profile from the project config file")
    parser.add_argument("-o", "--outFile", "--outfile", help="JUnit report output file, test_output.xml by default")
    parser.add_argument("--log", help="Folder path that contains test logs, test_result by default")
    parser.add_argument("--format", help="Format of log files, line by default", choices=['line', 'file'])
    parser.add_argument("--encoding", help="Encode of log files, utf-8 by default", choices=['utf-8', 'gbk'])

    args = parser.parse_args()
    return args

def VerifyResults(profile, projectConfig, logFilePattern, testCasePattern, passPattern, failPattern, blockPattern, skipPattern):
    '''
    verify the regular expresssions to ensure they're working as planned
    '''
    (logFilePatternTests, testCasePatternTests, passPatternTests, failPatternTests, blockPatternTests, skipPatternTests) = conf.GetConfigPatternTests(profile, projectConfig)
    if logFilePattern and logFilePatternTests:
        test("logFilePattern", logFilePattern, logFilePatternTests)
    if testCasePattern and testCasePatternTests:
        test("testCasePattern", testCasePattern, testCasePatternTests)
    if passPattern and passPatternTests:
        test("passPattern", passPattern, passPatternTests)
    if failPattern and failPatternTests:
        test("failPattern", failPattern, failPatternTests)
    if blockPattern and blockPatternTests:
        test("blockPattern", blockPattern, blockPatternTests)
    if skipPattern and skipPatternTests:
        test("skipPattern", skipPattern, skipPatternTests)

def test(name, pattern, tests):
    '''
    test pattern with provided test cases
    '''
    sysstr = platform.system()
    logging.debug("Testing %s: %s" % (name, pattern))
    for test in tests:
        expectedResult1 = ""
        expectedResult2 = ""
        if(sysstr == "Windows"):
            input = test["input"]
        elif(sysstr == "Linux"):
            input = test["input"].replace("\\", r'/')
            logging.debug("Convert test input to Linux style: %s" % input)
        else:
            logging.error("OS not supported")
            sys.exit(1)
        logging.debug("Data input: %s" % input)
        expectedResult1 = test["expectedResult1"]
        if "expectedResult2" in test:
            expectedResult2 = test["expectedResult2"]

        match = re.search(pattern, input, re.I)
        if not match and (expectedResult1 == "None" or expectedResult2 == "None"):
            logging.debug("Result: Pass")
            continue
        elif not match:
            logging.error("Something wrong with the %s: %s " % (name, pattern))
            sys.exit(1)
        else:
            if expectedResult1.lower() <> match.group(1).lower():
                logging.error("Something wrong with the %s: expectedResult1 is %s, while group(1) is %s." % (name, expectedResult1, match.group(1)))
                sys.exit(1)
            if "expectedResult2" in test:
                if expectedResult2.lower() <> match.group(2).lower():
                    logging.error("Something wrong with the %s: group(2)" % name)
                    sys.exit(1)
            logging.debug("Result: Pass")
    logging.info("Tests all passed for pattern %s" % name)

def ProcessLogFile(log, format, encoding, logFilePattern, testCasePattern, passPattern, failPattern, blockPattern, skipPattern):
    '''
    process the test log files by the provided regular expression patterns
    '''
    testSuites = defaultdict(list)
    if not os.path.exists(log):
        logging.error("Test log folder %s does not exist, please verify." % log)
        sys.exit(1)

    logging.info("Processing test log folder %s" % log)
    for dirpath, dirnames, filenames in os.walk(log):
        for result_file in filenames:
            #Check if the test log name is matching pre-defined pattern
            resultFileSearch = re.match(logFilePattern, os.path.join(dirpath, result_file), re.I)
            if resultFileSearch is None:
                #logging.debug("Skipping test log file %s" %  os.path.join(dirpath, result_file))
                continue
            else:
                logging.debug("Processing test log file %s" %  os.path.join(dirpath, result_file))
            fobj = open(os.path.join(dirpath, result_file), 'r')
            if format == "line":
                #Test result is stored in line, check each line
                (suiteName, className) = resultFileSearch.groups()
                row = 1
                for content in fobj:
                    if encoding == 'gbk':
                        content = content.decode('gbk')
                    testcaseSearch = re.match(testCasePattern, content, re.I)
                    #if the line is a record of a test result, try to find the test case name
                    if not content or content.strip() == '':
                        row += 1
                        continue
                    elif testcaseSearch is None:
                        logging.debug("No test match - %s[line:%d] - %s" % (fobj.name, row, content.strip()))
                        row += 1
                        continue
                    testName= testcaseSearch.group(1)
                    testStatusSearch = testStatusCheck(testSuites, suiteName, className, testName, content.strip(), passPattern, failPattern, blockPattern, skipPattern)
                    if not testStatusSearch:
                        logging.debug("No test status match - %s[line:%d]" % (fobj.name, row))
                    row += 1
            elif format == "file":
                #Test result is stored by file, check the whole file
                (suiteName, testName) = resultFileSearch.groups()
                content = fobj.read()
                if encoding == 'gbk':
                    content = content.decode('gbk')
                #Note the class name is ignored, use suite name instead
                testStatusSearch = testStatusCheck(testSuites, suiteName, suiteName, testName, content.strip(), passPattern, failPattern, blockPattern, skipPattern)
                if not testStatusSearch:
                        logging.debug("No test status match - %s" % fobj.name)
            else:
                logging.error("The specified test format %s is not supported yet" % format)
                sys.exit(1)
            fobj.close()

    junit_test_suites = []
    for suiteName, testCases in testSuites.items():
        junit_test_suites.append(TestSuite(suiteName, testCases))

    return junit_test_suites

def testStatusCheck(testSuites, suiteName, className, testName, content, passPattern, failPattern, blockPattern, skipPattern):
    """
    check test status in content, if test status identified, then add to the specified test suite
    :params testSuites: dictionary of test suites
    :params suiteName: test suite name
    :params className: test class name
    :params testName: test name
    :params content: test log content
    """
    matchPassed = re.search(passPattern, content, re.I)
    matchFailed = re.search(failPattern, content, re.I)
    matchBlocked = re.search(blockPattern, content, re.I)
    matchSkipped = re.search(skipPattern, content, re.I)

    if not (matchPassed or matchSkipped or matchFailed or matchBlocked):
        return False

    testcase = TestCase(testName, className, 0.01, content, 'I am stderr!')
    if matchSkipped:
        testcase.add_skipped_info('skipped message', 'skipped log')
    elif matchFailed:
        testcase.add_failure_info('failed message', 'failed log')
    elif matchBlocked:
        testcase.add_error_info('block message', 'blocked log', error_type="Blocked")
    elif not matchPassed:
        testcase.add_error_info('error message', 'error log')
    testSuites[suiteName].append(testcase)
    return True

def WriteTestResultsToJunit(outfile, junit_test_suites):
    '''
    write the test results to a JUnit file
    '''
    try:
        with open(outfile, 'w') as fileObj:
            TestSuite.to_file(fileObj, junit_test_suites, prettyprint=True)
    except IOError:
        logging.error("The JUnit output file %s cannot be opened." % outfile)
        sys.exit(1)
    logging.info("Save JUnit test report to %s" % outfile)

if __name__ == '__main__':
    main()
