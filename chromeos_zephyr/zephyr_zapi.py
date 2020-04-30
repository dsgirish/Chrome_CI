# -*- coding: utf-8 -*
#!/usr/bin/env python
'''
The purpose of this script is to upload the test results to JIRA/Zephyr.
The general flow of the script is the following:
1.Initialize the connection to JIRA/Zephyr.
2.Parse the JUnit test result files to prepare the data for upload.
3.Upload the test results to JIRA/Zephyr.
'''
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import argparse
import logging
import time
from collections import defaultdict

import conf
from zapi import ZAPI

def main():
    start_time = time.time()
    args = ParseArgs()
    conf.ConfigLogging(args.debug, args.verbose)
    projectConfig = {}
    projectConfig = conf.GetProjectConfig(args.config)
    args = conf.ApplyProjectConfigToArgs(args, projectConfig)
    (username, password) = conf.GetUserPassword(args.profile, projectConfig)
    conf.SetupEnvironment(args.cert)
    zapi = ZAPI(args.url, username, password, args.disableSSL, args.cert, args.maxRetry, args.timeout, \
        args.timeToAddATest, args.slicerToAddTests, args.slicerToUpdateExecutions)
    args.func(args, zapi, projectConfig)
    end_time = time.time()
    logging.info("Execution completes. Runtime: %s seconds" % (round(end_time - start_time)))

def ParseArgs():
    '''
    parse the arguments
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", help="Debug mode", action="store_true")
    parser.add_argument("-v", "--verbose", help="Verbose mode", action="store_true")
    parser.add_argument("--url", help="JIRA server URL, https://jira.devtools.intel.com by default")
    parser.add_argument("--cert", help="JIRA server certificate, use system environment variable REQUESTS_CA_BUNDLE by default")
    parser.add_argument("--disableSSL", "--disablessl", help="Disable SSL Verify", action="store_true")
    parser.add_argument("--config", help="Project config file, project_config.json by default", default='project_config.json')
    parser.add_argument("-p", "--profile", help="Choose the profile from the project config file")

    subparsers = parser.add_subparsers(title="subcommands", description='desc', help="Addtional help", dest='command')

    parser_execute = subparsers.add_parser('execute', help='Execute test')
    parser_execute.add_argument("-f", "--file", help="JUnit test result file, test_result.xml by default")
    parser_execute.add_argument("--zql", help="ZQL query")
    parser_execute.add_argument("--project", help="Project key in JIRA")
    parser_execute.add_argument("--fixVersion", "--fixversion", help="Fix version name in JIRA")
    parser_execute.add_argument("--cycleName", "--cyclename", help="Test cycle name in JIRA")
    parser_execute.add_argument("--newCycle", "--newcycle", action='store_true', help="Create a new test cyle")
    parser_execute.add_argument("--suite", help="Add/clone tests from a test suite")
    parser_execute.add_argument("--suiteFixVersion", "--suitefixversion", help="The fixVersion of a test suite")
    parser_execute.add_argument("--updateLatest", "--updatelatest", action='store_true',
                                help="Update the latest record if multiple entries exist for the same test name")
    parser_execute.add_argument("--startDate", "--startdate", help="Test cycle start date")
    parser_execute.add_argument("--endDate", "--enddate", help="Test cycle end date")
    parser_execute.add_argument("--build", help="Test cycle build information")
    parser_execute.add_argument("--environment", help="Test cycle environment information")
    parser_execute.add_argument("--description", help="Test cycle description")
    parser_execute.add_argument("--ignore", action='store_true',
                                help="Ignore test cases not listed in the specified test cycle")
    parser_execute.add_argument("--add", action='store_true',
                                help="Add existing tests to the specified test cycle")
    parser_execute.add_argument("--create", action='store_true',
                                help="Create new tests and add to the specified test cycle")
    parser_execute.add_argument("--updateComment", "--updatecomment", action='store_true',
                                help="Update the comments for tests")
    parser_execute.add_argument("--maxRetry", "--maxretry", 
                                help="Maximum retries for one API call, range from 5 to 300, 30 by default",
                                type=int, default=30)
    parser_execute.add_argument("--timeout", help="Time interval between API calls, ranges from 5 to 50 seconds, 10 by default",
                                type=int, default=10)
    parser_execute.add_argument("--timeToAddATest", "-tt",
                                help="Estimated average time to add a test to a test cycle, ranges from 1 to 10 seconds, 4 by default",
                                type=float, default=4)
    parser_execute.add_argument("--slicerToAddTests", "-st",
                                help="Test count to add tests to a test cycle by groups, ranges from 20 to 500 tests, 50 by default",
                                type=int, default=50)
    parser_execute.add_argument("--slicerToUpdateExecutions", "-se",
                                help="Execution count to update status to a test cycle by groups, ranges from 500 to 2000 executions, 1000 by default",
                                type=int, default=1000)
    parser_execute.set_defaults(func=execute)

    args = parser.parse_args()

    return args

def execute(args, zapi, projectConfig):
    '''
    execute the flow to upload test results to JIRA/Zephyr
    '''
    projectId = -1
    versionId = None
    cycleId = -1
    issueProject = ''
    expectedExecutionCount = 0

    #Check test cycle information
    (issueProject, projectId, fixVersion, versionId, cycleName, cycleId) = conf.SetupCycle(args,zapi)

    #Clone test executions from a test suite
    if args.suite:
        (fromCycleId, fromVersionId) = zapi.listCycles(projectId, args.suite, None, args.suiteFixVersion)
        if fromCycleId is not None:
            logging.debug("Clone tests from suite: %s, cycle id: %s, suite fixVersion: %s" % (args.suite, fromCycleId, fromVersionId))
        else:
            logging.error("Cannot find suite %s in this project, under version %s" % (args.suite, args.suiteFixVersion))
            sys.exit(1)
        expectedExecutionCount = zapi.getExecutionCountAfterMerge(cycleId, fromCycleId)
        zapi.addTestsToCycleFromSuite(cycleId, fromCycleId, projectId, versionId, fromVersionId)
        #extra check is required here to ensure these executions are turely added to the test cycle.
        #otherwise the following execution search won't be able to load all the executions.

    #Retrieve test executions from the test cycle
    executions = zapi.executeSearchWithExpectedCount(args.zql, expectedExecutionCount)
    logging.debug("Count of existing executions in the cycle: %d" % len(executions))
    executionIds = {}
    executionKeys = {}
    expectedExecutionCount = 0
    if executions:
        for execution in executions:
            executionIds[execution['issueSummary']] = execution['id']
            executionKeys[execution['issueSummary']] = execution['issueKey']
        expectedExecutionCount = len(executions)
        logging.debug("Expected execution count in test cyle: %d" % expectedExecutionCount)

    tests = conf.ParseJunit(args.file)

    #Check the the test result input, if --ignore is not used:
    #existingIssues: test cases exist in JIRA but not part of the test cycle
    #newTests: test cases don't exist in JIRA and not part of the test cycle
    existingIssues = []
    newTests = []
    if not args.ignore:
        #Retrieve all the test cases from the JIRA project, to accelerate the process
        projectTestCases = {}
        testCounts = {}
        (projectTestCases, testCounts) = GetProjectTestInfo(issueProject,zapi)
        (existingIssues, newTests) = IdentifyTestSets(args, tests, executionIds, projectTestCases, testCounts)

    #Add existing issues to the test cycle
    if not args.ignore and args.add:
        if len(existingIssues) > 0:
            zapi.addTestsToCycleBySlicer(existingIssues, cycleId, projectId, versionId)
            expectedExecutionCount += len(existingIssues)
            logging.debug("Expected execution count after adding existing tests to the test cycle: %d" % expectedExecutionCount)

    #Create the new tests, and add them to the test cycle
    newIssues = []
    issues = []
    if not args.ignore and args.create:
        if len(newTests) > 0:
            issues = ConstructNewIssueInfo(args.profile, issueProject, projectConfig, newTests)
        if len(issues) > 0:
            newIssues = zapi.createTestIssues(issues)
            if len(newIssues) > 0:
                zapi.addTestsToCycleBySlicer(newIssues, cycleId, projectId, versionId)
                expectedExecutionCount += len(newIssues)
                logging.debug("Expected execution count after adding new tests to the test cycle: %d" % expectedExecutionCount)

    #If adding or creating any new tests to the test cycle, refresh the list of executions
    if len(newTests) > 0 or len(existingIssues) > 0:
        executions = zapi.executeSearchWithExpectedCount(args.zql, expectedExecutionCount)
        if executions:
            executionIds.clear()
            executionKeys.clear()
            for execution in executions:
                executionIds[execution['issueSummary']] = execution['id']
                executionKeys[execution['issueSummary']] = execution['issueKey']

    zapi.updateExecutionStatusBySlicer(tests, executionIds)

    if args.updateComment:
        tests = conf.GetComments(args.file)
        logging.info("Adding comments to issues...")
        for test in tests:
            if "comment" in test and len(test["comment"]) > 0 and test["summary"] in executionKeys:
                zapi.addComment(executionKeys[test["summary"]], test["comment"])

def GetProjectTestInfo(issueProject,zapi):
    '''
    Retrieve all the test cases from the project, to accelerate the check process
    :return: a list of project test cases
    '''
    testCases = []
    jql = "project = " + issueProject + " AND issuetype = test "
    testCases = zapi.executeJqlSearch(jql)
    projectTestCases = {}
    testCounts = {}
    duplicateTestCountInProject = 0
    for ts in testCases:
        if ts["fields"]["summary"] not in projectTestCases:
            projectTestCases[ts["fields"]["summary"]] = ts["key"]
            testCounts[ts["fields"]["summary"]] = 1
        else:
            testCounts[ts["fields"]["summary"]] += 1
            duplicateTestCountInProject += 1
    logging.info("Total test cases in this project: %d" % len(projectTestCases))
    logging.info("Duplicate test cases in this project: %d" % duplicateTestCountInProject)
    return (projectTestCases, testCounts)

def IdentifyTestSets(args, tests, executionIds, projectTestCases, testCounts):
    '''
    Identify test sets by comparing the JUnit test results, test cycle 
    executions and all test cases in the JIRA project
    :params tests: JUnit test results
    :params executionIds: a dictionary of test execution Ids by issue summary
    :params projectTestCases: all test cases in the JIRA project
    :return: a list of project test cases
    '''
    existingIssues = []
    newTests = []
    duplicateTestCountFromZephyr = 0
    testExistNotInExecution = None
    testNonExist = None
    for test in tests:
        summary = test['summary']
        if summary not in executionIds:
            if summary in projectTestCases:
                issue_count = testCounts[summary]
                if issue_count > 1:
                    duplicateTestCountFromZephyr += 1
                    if not args.updateLatest:
                        continue
                    else:
                        #Always use the latest key to update if duplicate entries exist
                        testExistNotInExecution = True
                        existingIssues.append(projectTestCases[summary])
                elif issue_count == 1:
                    testExistNotInExecution = True
                    existingIssues.append(projectTestCases[summary])
            else:
                testNonExist = True
                if 'description' in test:
                    newTests.append((summary, test['description']))
                else:
                    newTests.append((summary, None))

    if duplicateTestCountFromZephyr > 0:
        if not args.updateLatest:
            logging.warn('Test results matching duplicate tests in JIRA are ignored: %d' % duplicateTestCountFromZephyr)
        else:
            logging.info('Test results matching duplicate tests in JIRA: %d' % duplicateTestCountFromZephyr)
    if testExistNotInExecution and testNonExist and not args.add and not args.create:
        logging.error("Some tests don't exist, and some tests exist but they're not part of the specified test cycle.\n"
                        + "\tPlease use --create to create the tests and add to the specified test cyle,\n"
                        + "\tor use --add to add the tests to the specified test cyle.\n"
                        + "\tor use --ignore to skip thest tests.")
        sys.exit(1)
    if not testExistNotInExecution and testNonExist and not args.create:
        logging.error("Some tests don't exist.\n"
                        + "\tPlease use --create to create the tests and add to the specified test cyle,\n"
                        + "\tor use --ignore to skip thest tests.")
        sys.exit(1)
    if not args.add and testExistNotInExecution and not testNonExist:
        logging.error("Some tests exist but they're not part of the specified test cycle.\n"
                        + "\tPlease use --add to add the tests to the specified test cyle,\n"
                        + "\tor use --ignore to skip thest tests.")
        sys.exit(1)

    logging.debug("length of existingIssues in JIRA but not in cycle: %d" % len(existingIssues))
    logging.debug("length of newTests not in JIRA: %d" % len(newTests))

    return (existingIssues, newTests)

def ConstructNewIssueInfo(profile, issueProject, projectConfig, newTests):
    '''
    Prepare the json data of the new tests
    '''
    issues = []
    config = {}
    if profile and projectConfig and 'jiraConfig' in projectConfig[profile]:
        config = projectConfig[profile]['jiraConfig']
    for (summary, description) in newTests:
        issue = {
            "project": {
                "key": issueProject
            },
            "summary": summary,
            "issuetype": {
                "name": "Test"
        }
        }
        #Change required: this part is actually not implemented yet in ParseJunit, so no input would be put into description
        if description <> None:
            issue['description'] = description

        for key, value in config.items():
            if key == "project" or key == "fixVersion" or key == "cycleName":
                continue
            if key.find("comment") != -1:
                continue
            if key == "description" and description <> None:
                continue
            issue[key] = value

        issues.append({"fields": issue})

    return issues

if __name__ == '__main__':
    main()