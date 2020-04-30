# -*- coding: utf-8 -*
#!/usr/bin/env python
'''
The purpose of this script is to help the testing of zephyr_zapi.py and zapi.py scripts. By 
calling the subcommand delete, you can delete a test cycle or a group of test issues from JIRA.
Use this sciprt wisely.
'''
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import os
import argparse
import re
import logging
import json
import time
import xlsxwriter
import xlrd

from zapiext import ZAPIEXT
#add the parent folder to system path
sys.path.append( os.path.split((os.path.split( os.path.realpath( sys.argv[0] ) )[0]))[0])
import conf

def main():
    start_time = time.time()
    args = ParseArgs()
    conf.ConfigLogging(args.debug, args.verbose)
    projectConfig = {}
    projectConfig = conf.GetProjectConfig(args.config)
    args = conf.ApplyProjectConfigToArgs(args, projectConfig)
    (username, password) = conf.GetUserPassword(args.profile, projectConfig)
    conf.SetupEnvironment(args.cert)
    zapi = ZAPIEXT(args.url, username, password, args.disableSSL, args.cert)
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
    parser.add_argument("--cert", help="JIRA server certificate, use system environnment variable REQUESTS_CA_BUNDLE by default")
    parser.add_argument("--disableSSL", "--disablessl", help="Disable SSL Verify", action="store_true")
    parser.add_argument("-c", "--config", help="Project config file, project_config.json by default", default='project_config.json')
    parser.add_argument("-p", "--profile", help="Choose the profile from the project config file")

    subparsers = parser.add_subparsers(title="subcommands", description='desc', help="Addtional help", dest='command')

    parser_traceability = subparsers.add_parser('traceability', help='Export traceability matrix')
    parser_traceability.add_argument("-o", "--output", type=argparse.FileType('w'),
                                help="Traceability file, csv format by default")
    parser_traceability.add_argument("--jql", help="JQL query")
    parser_traceability.add_argument("--zql", help="ZQL query")
    parser_traceability.add_argument("--fromrequirement", "--fromRequirement", action='store_true',
                                help="Query traceability matrix from requirement to defect")
    parser_traceability.add_argument("--fromdefect", "--fromDefect", action='store_true',
                                help="Query traceability matrix from defect to requirement")
    parser_traceability.add_argument("--fromexecution", "--fromExecution", action='store_true',
                                help="Query traceability matrix from execution to requirement")
    parser_traceability.set_defaults(func=traceability)

    parser_maintenance = subparsers.add_parser('maintenance', help='Upload and maintain test cases')
    parser_maintenance.add_argument("-f", "--file", help="Test case file, testcase_input.xlsx by default")
    parser_maintenance.add_argument("--zql", help='ZQL query, if unspecified, test execution update will be ignored. \
                                ZQL format: project = "EETRACEBIM" AND fixVersion = "VER1" AND cycleName in ("test cycle name")')
    parser_maintenance.add_argument("--project", help="JIRA Project Key")
    parser_maintenance.add_argument("--fixVersion", "--fixversion", help="Fix version")
    parser_maintenance.add_argument("--cycleName", "--cyclename", help="Test cycle name")
    parser_maintenance.add_argument("--newCycle", "--newcycle", action='store_true', help="Create a new test cyle")
    parser_maintenance.add_argument("--updateLatest", "--updatelatest", action='store_true',
                                help="Update the latest record if multiple entries exist in JIRA with the same test name")
    parser_maintenance.add_argument("--startDate", "--startdate", help="Test cycle start date")
    parser_maintenance.add_argument("--endDate", "--enddate", help="Test cycle end date")
    parser_maintenance.add_argument("--build", help="Test cycle build information")
    parser_maintenance.add_argument("--environment", help="Test cycle environment information")
    parser_maintenance.add_argument("--description", help="Test cycle description")
    parser_maintenance.add_argument("--skipUpdate", "--skipupdate", action='store_true',
                                help="Skip the update for test cases and test steps")
    parser_maintenance.add_argument("--skipStepUpdate", "--skipstepupdate", action='store_true',
                                help="Skip the update for test steps")
    parser_maintenance.add_argument("--ignore", action='store_true', help="Ignore new tests")
    parser_maintenance.add_argument("--updateLink", "--updatelink", action='store_true',
                                help="Overwrite the links, if unspecified, append links only. \
                                If no issue key provided in the sheet, no action will be taken. \
                                If any issue key provided, then all links of same link type will be overwriten. \
                                Use this option wisely. ")
    parser_maintenance.add_argument("--updateComment", "--updatecomment", action='store_true',
                                help="Update the comments for tests")
    parser_maintenance.add_argument("--updateExecution", "--updateexecution", action='store_true', help="Update test executions in a test cycle")
    parser_maintenance.add_argument("--updateStepExecution", "--updatestepexecution", action='store_true', help="Update test step executions in a test cycle")
    parser_maintenance.set_defaults(func=maintenance)

    parser_export = subparsers.add_parser('export', help='Export test cases')
    parser_export.add_argument("-o", "--output", help="Test case file, exported_testcases.csv or exported_testcases.xlsx by default")
    parser_export.add_argument("--format", help="Test case file format, csv(default) or xlsx", choices=['csv', 'xlsx'], default="csv")
    parser_export.add_argument("--zql", help="ZQL query")
    parser_export.add_argument("--project", help="JIRA Project Key")
    parser_export.add_argument("--fixVersion", "--fixversion", help="Fix version")
    parser_export.add_argument("--cycleName", "--cyclename", help="Test cycle name")
    parser_export.add_argument("--addTitle", "--addtitle", action='store_true', 
                               help="Export to csv with field names as title, it only works with --zql.")
    parser_export.add_argument("--jql", help="JQL query")
    parser_export.add_argument("--fields", help="You can add the fields you want to query, it only works with --jql.", \
        default="summary,description,priority,status,assignee,severity,operating system/s,labels,affects version/s,fix version/s,issue viewers")
    parser_export.add_argument("--testSteps", "--teststeps", action='store_true', 
                               help="Export with test steps for tests")

    parser_export.set_defaults(func=export)

    parser_delete = subparsers.add_parser('delete', help='Delete a test cycle by ZQL, or delete test issues by JQL')
    parser_delete.add_argument("--type", choices=['cycle', 'test'], help="For cycle, --zql or (--project, --fixVersion, "
                               + "--cycleName) should be specified. For test, --jql must be specified")
    parser_delete.add_argument("--zql", help="ZQL query, if unspecified, test execution update will be ignored. \
                                ZQL format: project = 'EETRACEBIM' AND fixVersion = 'VER1' AND cycleName in ('test cycle name')")
    parser_delete.add_argument("--project", help="JIRA Project Key")
    parser_delete.add_argument("--fixVersion", "--fixversion", help="Fix version")
    parser_delete.add_argument("--cycleName", "--cyclename", help="Test cycle name")
    parser_delete.add_argument("--jql", help="JQL query")
    parser_delete.set_defaults(func=delete)

    parser_verify = subparsers.add_parser('verify', help='Verify the ZQL parser in the conf.py scripts')
    parser_verify.add_argument("--zql", help="ZQL query, if unspecified, test execution update will be ignored. \
                                ZQL format: project = 'EETRACEBIM' AND fixVersion = 'VER1' AND cycleName in ('test cycle name')")
    parser_verify.add_argument("--project", help="JIRA Project Key")
    parser_verify.add_argument("--fixVersion", "--fixversion", help="Fix version")
    parser_verify.add_argument("--cycleName", "--cyclename", help="Test cycle name")
    parser_verify.set_defaults(func=verifyZQLParser)

    args = parser.parse_args()
    return args

def traceability(args, zapi, projectConfig):
    '''
    subcommand traceability, to generate traceability matrix by a ZQL or JQL query
    '''
    if args.fromrequirement and args.jql is None:
        logging.error("Please specify the JQL query for exporting traceability matrix from requirements")
        sys.exit(1)
    elif args.fromdefect and args.jql is None:
        logging.error("Please specify the JQL query for exporting traceability matrix from defects")
        sys.exit(1)
    elif args.fromexecution and args.zql is None:
        logging.error("Please specify the ZQL query for exporting traceability matrix from executions")
        sys.exit(1)
    elif not args.fromrequirement and not args.fromdefect and not args.fromexecution:
        logging.error("no action taken, please specify the tracebilty parameter")
        sys.exit(1)

    if args.fromrequirement:
        generateMatrixFromRequirement(zapi, args.url, args.jql, args.output)
    elif args.fromdefect:
        generateMatrixFromDefect(zapi, args.url, args.jql, args.output)
    elif args.fromexecution:
        generateMatrixFromExecution(zapi, args.url, args.zql, args.output)
    else:
        logging.error("no action taken, please specify the traceability parameter")
        sys.exit(1)

def generateMatrixFromRequirement(zapi, url, jql, outputFile):
    '''
    generate the traceability matrix table from requirements, which are speicified by a JQL query.
    '''
    #Check output file
    if outputFile is None:
        outputFile = "traceability_from_requirement.xlsx"
    #Generate the flat format to the output file
    jiraUrl = url + "browse/"

    #Retrieve the list of requirements from jql
    requirements = []
    requirements = zapi.executeJqlSearch(jql)
    requirementKeyList = []
    for requirement in requirements:
        requirementKeyList.append(requirement["key"])
    #Retrieve the traceablilty data for the requirements
    issues = []
    issues = zapi.testsByRequirement(requirementKeyList)

    workbook = xlsxwriter.Workbook(outputFile)
    worksheet = workbook.add_worksheet(u"traceability matrix")
    headings = ["Req", "ReqSummary", "Test", "TestSummary", "Defect", "DefectStatus", "DefectSummary", "FailedCount", "PassCount"]
    worksheet.write_row("A1", headings)

    row=1
    for issue in issues:
        requirementKey = issue["requirement"]["key"]
        requirementSummary = issue["requirement"]["summary"]
        tests = issue["tests"]

        #if no test linked, output the requirement and continue
        if len(tests) == 0:
            col=0
            worksheet.write_url(row, col, jiraUrl+requirementKey, string=requirementKey)
            col+=1
            worksheet.write(row, col, requirementSummary)
            row+=1
            continue

        #if linked to tests
        for test in tests:
            testKey = test["test"]["key"]
            testSummary = test["test"]["summary"]
            defects = test["defects"]
            statuses = test["executionStat"]["statuses"]
            failCount = 0
            passCount = 0
            for status in statuses:
                if status["status"] == "FAIL":
                    failCount = status["count"]
                elif status["status"] == "PASS":
                    passCount = status["count"]
            for defect in defects:
                col=0
                worksheet.write_url(row, col, jiraUrl+requirementKey, string=requirementKey)
                col+=1
                worksheet.write(row, col, requirementSummary)
                col+=1
                worksheet.write_url(row, col, jiraUrl+testKey, string=testKey)
                col+=1
                worksheet.write(row, col, testSummary)
                col+=1
                worksheet.write_url(row, col, jiraUrl+defect["key"], string=defect["key"])
                col+=1
                worksheet.write(row, col, defect["status"])
                col+=1
                worksheet.write(row, col, defect["summary"])
                col+=1
                worksheet.write(row, col, failCount)
                col+=1
                worksheet.write(row, col, passCount)
                col+=1
                row+=1
    workbook.close()

def generateMatrixFromDefect(zapi, url, jql, outputFile):
    '''
    generate the traceability matrix table from defects, which are speicified by a JQL query.
    '''
    #Check output file
    if outputFile is None:
        outputFile = "traceability_from_defect.xlsx"

    workbook = xlsxwriter.Workbook(outputFile)
    worksheet = workbook.add_worksheet(u"traceability matrix")
    headings = ["DefectKey", "ExecutionId", "ExecutionStatus", "TestCycle", "TestKey", "TestSummary", "ReqKey", "ReqSummary"]
    worksheet.write_row("A1", headings)
    #Generate the flat format to the output file
    jiraUrl = url + "browse/"
    jiraExecutionUrl = url + "secure/enav/#/"

    #Retrieve the list of defects from jql
    defects = []
    defects = zapi.executeJqlSearch(jql)
    defectKeyList = []
    for defect in defects:
        defectKeyList.append(defect["key"])

    row=1
    for defectKey in defectKeyList:
        #Retrieve the traceablilty data for the requirements
        issues = []
        res = zapi.executionsByDefect(defectKey)
        issues = res["executions"]

        #if no execution at all, output the defect key and continue
        if len(issues) == 0:
            col=0
            worksheet.write_url(row, col, jiraUrl+defectKey, string=defectKey)
            row+=1
            continue

        #if any executions exist
        for issue in issues:
            requirements = issue["requirement"]
            executionId = issue["execution"]["id"]
            executionStatus = issue["execution"]["status"]
            executionTestCycle = issue["execution"]["testCycle"]
            testKey = issue["test"]["key"]
            testSummary = issue["test"]["summary"]

            #if no requirements linked, output the execution, test case and continue
            if len(requirements) == 0:
                col=0
                worksheet.write_url(row, col, jiraUrl+defectKey, string=defectKey)
                col+=1
                worksheet.write_url(row, col, jiraExecutionUrl+executionId, string=executionId)
                col+=1
                worksheet.write(row, col, executionStatus)
                col+=1
                worksheet.write(row, col, executionTestCycle)
                col+=1
                worksheet.write_url(row, col, jiraUrl+testKey, string=testKey)
                col+=1
                worksheet.write(row, col, testSummary)
                row+=1
                continue

            #if linked to requirements
            for requirement in requirements:
                requirementKey = requirement["key"]
                requirementSummary = requirement["summary"]
                col=0
                worksheet.write_url(row, col, jiraUrl+defectKey, string=defectKey)
                col+=1
                worksheet.write_url(row, col, jiraExecutionUrl+executionId, string=executionId)
                col+=1
                worksheet.write(row, col, executionStatus)
                col+=1
                worksheet.write(row, col, executionTestCycle)
                col+=1
                worksheet.write_url(row, col, jiraUrl+testKey, string=testKey)
                col+=1
                worksheet.write(row, col, testSummary)
                col+=1
                worksheet.write_url(row, col, jiraUrl+requirementKey, string=requirementKey)
                col+=1
                worksheet.write(row, col, requirementSummary)
                row+=1
    workbook.close()

def generateMatrixFromExecution(zapi, url, zql, outputFile):
    '''
    generate the traceability matrix table from executions, which are speicified by a ZQL query.
    '''
    #Check output file
    if outputFile is None:
        outputFile = "traceability_from_execution.xlsx"

    #Retrieve the list of executions from the test cycle
    executions = zapi.executeSearchWithExpectedCount(zqlQuery=zql)
    workbook = xlsxwriter.Workbook(outputFile)
    worksheet = workbook.add_worksheet(u"traceability matrix")
    headings = ["DefectKey", "ExecutionId", "ExecutionStatus", "TestCycle", "TestKey", "TestSummary", "ReqKey", "ReqSummary"]
    worksheet.write_row("A1", headings)
    #Generate the flat format to the output file
    jiraUrl = url + "browse/"
    jiraExecutionUrl = url + "secure/enav/#/"

    row=1
    for execution in executions:
        defects = []
        defects = execution["executionDefects"]
        executionId = str(execution["id"])
        executionStatus = execution["status"]["name"]
        executionTestCycle = execution["cycleName"]
        testKey = execution["issueKey"]
        testSummary = execution["issueSummary"]

        #if no defect at all
        if len(defects) == 0:
            col=0
            worksheet.write_url(row, col, "")
            col+=1
            worksheet.write_url(row, col, jiraExecutionUrl+executionId, string=executionId)
            col+=1
            worksheet.write(row, col, executionStatus)
            col+=1
            worksheet.write(row, col, executionTestCycle)
            col+=1
            worksheet.write_url(row, col, jiraUrl+testKey, string=testKey)
            col+=1
            worksheet.write(row, col, testSummary)
            row+=1
            continue

        #if any defects exist
        for defect in defects:
            defectKey = defect["defectKey"]
            #Retrieve the traceablilty data for the requirements
            issues = []
            res = zapi.executionsByDefect(defectKey)
            issues = res["executions"]

            #At least one execution exists
            for issue in issues:
                if executionId != issue["execution"]["id"]:
                    continue
                requirements = issue["requirement"]

                #if linked to requirements
                for requirement in requirements:
                    requirementKey = requirement["key"]
                    requirementSummary = requirement["summary"]
                    col=0
                    worksheet.write_url(row, col, jiraUrl+defectKey, string=defectKey)
                    col+=1
                    worksheet.write_url(row, col, jiraExecutionUrl+executionId, string=executionId)
                    col+=1
                    worksheet.write(row, col, executionStatus)
                    col+=1
                    worksheet.write(row, col, executionTestCycle)
                    col+=1
                    worksheet.write_url(row, col, jiraUrl+testKey, string=testKey)
                    col+=1
                    worksheet.write(row, col, testSummary)
                    col+=1
                    worksheet.write_url(row, col, jiraUrl+requirementKey, string=requirementKey)
                    col+=1
                    worksheet.write(row, col, requirementSummary)
                    row+=1
    workbook.close()

def maintenance(args, zapi, projectConfig):
    """
    Test case maintenance between a test spreadsheet and a JIRA project, test 
    cases are identified by the test name (summary field in JIRA).
    """
    if args.project is None:
        logging.error("Please specify the JIRA project key for maintenance by --project or in the config file.")
        sys.exit(1)

    #Retrieve all the test issues from the JIRA project, to accelerate the process
    jiraIssues = {}

    jql = "project = " + args.project + " AND issuetype = test "
    if args.skipUpdate and not args.updateLink and not args.updateExecution \
        and not args.updateStepExecution and not args.updateComment:
        logging.info("No action required, please check your command options.")
        sys.exit(0)
    else:
        jiraIssues = GetJiraIssues(zapi, jql)

    logging.info("Loading tests from %s..." % args.file)
    tests = parse_xlsx(args.file, projectConfig)

    logging.info("Identifying test sets...")
    existingIssues = []
    newTests = []
    (existingIssues, newTests) = IdentifyTestSets(tests, jiraIssues, args.updateLatest)

    newIssues = []
    if not args.skipUpdate and not args.ignore and len(newTests) > 0:
        logging.info("Creating new test cases...")
        issues = ConstructNewIssues(args.project, newTests)
        newIssues = zapi.createTestIssues(issues, 'issue')
        logging.info("Refreshing JIRA issues...")
        jiraIssues = GetJiraIssues(zapi, jql)
        logging.info("Creating new test steps...")
        CreateTestSteps(zapi, newIssues, jiraIssues, newTests)

    if not args.skipUpdate and len(existingIssues) > 0:
        UpdateIssues(zapi, existingIssues, args.skipStepUpdate)

    if args.updateLink:
        logging.info("Creating/updating issue links...")
        MaintainIssueLinks(args, zapi, tests, jiraIssues)

    #Update test step execution status
    #To be implemented
    if args.updateStepExecution:
        logging.info("Updating step execution status...")
        logging.info("This functionality is not implemented yet.")
        pass

    if args.updateComment:
        logging.info("Adding comments and summarized comments of step execution status to issues...")
        UpdateComment(zapi, tests, jiraIssues)

    if args.updateExecution and args.zql:
        UpdateExecution(args, zapi, existingIssues, newIssues, tests)
    elif args.updateExecution and not args.zql:
        logging.error("Please specify --zql in the command line, or specify \
        --project, --fixversion, --cyclename in the command line, or add \
        project, fixVersion, cycleName information in the project config file.")
        sys.exit(1)

def parse_xlsx(file, projectConfig):
    """
    parse xlsx test result for test case maintenance
    :params file: the test case file
    :params projectConfig: the project config
    :returns: a list of tests
    The xlsx format, if OrderID is empty, then the step on the same row will be ignored:
    Name    Desription  OrderId Step    Data    Execution status    is a test for   status  ...
    test1   des         1       step1   data1   result1             key1, key2      pass    ...
    test2   des         1       step1   data1   result1             key3            fail    ...
                        2       step2   data2   result2                             block   ...
    test3   des         1       step1   data1   result1                             no run  ...
    """
    data = xlrd.open_workbook(file)
    table = data.sheets()[0]
    colnames = table.row_values(0)
    for i in range(len(colnames)):
        colnames[i] = colnames[i].strip().lower()
    nrows = table.nrows
    tests = []
    rownum = 1
    colnum = 0
    stepPattern = r'(orderid|step|data|result|step execution status|step execution defects|step execution comment)$'
    linkPattern = r'(is tested by|is a test for|duplicates|is duplicated by|blocks|is blocked by|clones|is cloned by|affects versions|fix versions|issue viewers|execution defects|components|operating systems)$'
    while rownum < nrows:
        row = table.row_values(rownum)
        teststepSummary = ''
        addTeststepSummary = False
        addOverallSummary = False
        if row:
            test = {}
            if row[0].strip() == '':
                continue
            else:
                teststeps = []
                stepStatus = ''
                teststep = {}
                for i in range(len(colnames)):
                    #print("processing row %d, column %d" % (rownum, i))
                    if row[i] is not None and str(row[i]).strip() <> '':
                        if re.match(stepPattern, colnames[i]):
                            if colnames[i] == 'step execution status':
                                status = row[i].strip()
                                if status in projectConfig["jiraServerConfig"]["stepExecutionStatus"]:
                                    statusId = projectConfig["jiraServerConfig"]["stepExecutionStatus"][status]
                                    if status <> 'no run' and status <> 'pass':
                                        addTeststepSummary = True
                                        addOverallSummary = True
                                        stepStatus = status
                                else:
                                    logging.error("file %s, row %d, column %d: step execution status '%s' is not supported" % (file, rownum, i, status))
                                    sys.exit(1)
                                teststep[colnames[i]] = statusId
                            elif colnames[i] == 'step execution defects':
                                teststep[colnames[i]] = [item.strip() for item in row[i].split(",")]
                            elif isinstance(row[i], float):
                                teststep[colnames[i]] = int(row[i])
                            else:
                                teststep[colnames[i]] = str(row[i])
                        elif re.match(linkPattern, colnames[i]):
                            list = row[i].split(",")
                            list = [item.strip() for item in list]
                            test[colnames[i]] = list
                        elif colnames[i] == 'execution status':
                            status = row[i].strip()
                            if status in projectConfig["jiraServerConfig"]["executionStatus"]:
                                statusId = projectConfig["jiraServerConfig"]["executionStatus"][status]
                            else:
                                statusId = '6'
                            test[colnames[i]] = statusId
                        else:
                            if isinstance(row[i], float):
                                test[colnames[i]] = int(row[i])
                            else:
                                test[colnames[i]] = row[i]
                if len(teststep) > 0:
                    if teststep["orderid"]:
                        teststeps.append(teststep)
                        if addTeststepSummary:
                            teststepSummary += 'Step' + str(teststep['orderid']) + ' ' + stepStatus + '. '
                            stepStatus = ''
                #if the test name of the next row is empty, it means it's another test step of current test case
                while rownum + 1 < nrows:
                    row = table.row_values(rownum + 1)
                    addTeststepSummary = False
                    if row[0].strip() <> '':
                        break
                    else:
                        teststep = {}
                        for i in range(len(colnames)):
                            if row[i] is not None and str(row[i]).strip() <> '':
                                if re.match(stepPattern, colnames[i]):
                                    if colnames[i] == 'step execution status':
                                        status = row[i].strip()
                                        if status in projectConfig["jiraServerConfig"]["stepExecutionStatus"]:
                                            statusId = projectConfig["jiraServerConfig"]["stepExecutionStatus"][status]
                                            if status <> 'no run' and status <> 'pass':
                                                addTeststepSummary = True
                                                addOverallSummary = True
                                                stepStatus = status
                                        else:
                                            logging.error("file %s, row %d: step execution status %s is not supported" % (file, i, status))
                                            sys.exit(1)
                                        teststep[colnames[i]] = statusId
                                    elif colnames[i] == 'step execution defects':
                                        teststep[colnames[i]] = [item.strip() for item in row[i].split(",")]
                                    elif isinstance(row[i], float):
                                        teststep[colnames[i]] = int(row[i])
                                    else:
                                        teststep[colnames[i]] = str(row[i])
                        if len(teststep) > 0:
                            if teststep["orderid"]:
                                teststeps.append(teststep)
                                if addTeststepSummary:
                                    teststepSummary += 'Step' + str(teststep['orderid']) + ' ' + stepStatus + '. '
                                    stepStatus = ''
                    rownum += 1
                if len(teststeps) > 0:
                    test['teststeps'] = teststeps
                    if addOverallSummary:
                        test['teststepSummary'] = teststepSummary
            tests.append(test)
        rownum += 1
    #for test in tests:
    #    print json.dumps(test, indent=4)
    #sys.exit(1)
    return tests

def export(args, zapi, projectConfig):
    '''
    export test cases to a csv file or a xlsx file
    '''
    if args.output is not None:
        outputFile = args.output
    elif args.format == 'csv':
        outputFile = "exported_testcases.csv"
    elif args.format == 'xlsx':
        outputFile = "exported_testcases.xlsx"

    tests = []
    fields = []
    jiraField = zapi.getJiraField()
    if args.zql is None and args.jql is None:
        logging.error("Please specify the ZQL or JQL query for exporting JIRA issues")
        sys.exit(1)
    elif args.zql and not args.jql:
        fields = ["summary"]
        executions = zapi.executeSearchWithExpectedCount(zqlQuery=args.zql)
        for execution in executions:
            test = {}
            test["key"] = execution["issueKey"]
            test["summary"] = execution["issueSummary"]
            tests.append(test)
    elif args.jql and not args.zql:
        fields = [field.strip() for field in args.fields.decode("gbk").lower().encode("gbk").decode('string_escape').decode("gbk").split(",")]
        if "key" in fields:
            fields.remove("key")
        if "summary" not in fields:
            fields.append("summary")
        fieldsRaw = ','.join([jiraField[name]["id"] for name in fields])
        issues = zapi.executeJqlSearch(args.jql, fieldsRaw)
        tests = ParseJiraSearchResult(zapi, issues, fields, jiraField, args.testSteps)
        #for test in tests:
        #    print json.dumps(test, indent=4)
        #sys.exit(1)
    else:
        logging.error("ZQL and JQL query cannot be used at the same time.")
        sys.exit(1)

    if args.format == "csv":
        WriteTestsToCSV(outputFile, tests, fields, args.url, args.testSteps, args.addTitle)
    elif args.format == "xlsx":
        WriteTestsToWorkbook(outputFile, tests, fields, args.url, args.testSteps)

def ParseJiraSearchResult(zapi, issues, fields, jiraField, exportTestSteps):
    """
    parse the test result returned from JIRA Search, and convert them into simple dictionary
    :params issues: the JIRA search results
    :params fields: the fields to convert for
    :params jiraField: the JIRA field details
    :returns: a simple dictionary of JIRA tickets
    """
    unsupportedJiraFields = ["watches", "votes", "linked issues", "images", \
        "timetracking", "comment", "Code Complete Version", "Release Version History"]
    notifyUser = False
    tests = []
    for issue in issues:
        test = {}
        test["key"] = issue["key"]
        testId = issue["id"]
        for fieldName in fields:
            fieldId = jiraField[fieldName]["id"]
            fieldData = None
            fieldType = None
            if fieldId in issue["fields"]:
                fieldData = issue["fields"][fieldId]
            if "schema" in jiraField[fieldName]:
                fieldType = jiraField[fieldName]["schema"]["type"]
            value = ""
            if fieldData is not None:
                if fieldName == "labels":
                    value = ','.join(fieldData)
                elif fieldType == "array":
                    if len(fieldData) > 0 and "name" in fieldData[0]:
                        value = ','.join([item["name"] for item in fieldData])
                    elif len(fieldData) > 0 and "value" in fieldData[0]:
                        value = ','.join([item["value"] for item in fieldData])
                elif fieldType == "string" or fieldType == "any":
                    value = fieldData
                elif fieldType == "number":
                    value = fieldData
                elif fieldType == "progress":
                    if "percent" in fieldData:
                        value = fieldData["percent"]
                    else:
                        value = 0
                elif fieldType == "option-with-child":
                    value = fieldData["value"] + " - " + fieldData["child"]["value"]
                elif fieldType == "datetime":
                    value = time.strftime('%d/%b/%y %I:%M %p', time.strptime(fieldData[:-9], '%Y-%m-%dT%H:%M:%S'))
                elif fieldType == "date":
                    value = time.strftime('%d/%b/%y', time.strptime(fieldData, '%Y-%m-%d'))
                elif fieldType in unsupportedJiraFields:
                    notifyUser = True
                    pass
                else:
                    if "name" in fieldData:
                        value = fieldData["name"]
                    elif "value" in fieldData:
                        value = fieldData["value"]
                    else:
                        logging.error("Cannot find field %s, please verify." % fieldName)
                        sys.exit(1)
            #logging.debug("%s : %s" % (fieldName, value))
            test[fieldName] = value

        if exportTestSteps:
            #Query test steps
            teststeps = zapi.getTestSteps(testId)
            #Extract information from teststeps
            extracted_teststeps = []
            for teststep in teststeps:
                extracted_teststep = {}
                extracted_teststep["orderid"] = teststep["orderId"]
                extracted_teststep["step"] = teststep["step"]
                extracted_teststep["data"] = teststep["data"]
                extracted_teststep["result"] = teststep["result"]
                extracted_teststeps.append(extracted_teststep)
            if len(extracted_teststeps) > 0:
                test['test steps'] = extracted_teststeps

        tests.append(test)
    if notifyUser:
        logging.info("Field types \"%s\" are not supported by export command yet." % unsupportedJiraFields)
    return tests

def WriteTestsToWorkbook(file, tests, fields, url, exportTestSteps):
    """
    write JSON test data to a .xlsx file
    :params file: the output file of test cases
    :params tests: the JSON data of test cases
    The xlsx format:
    key     summary desription  OrderId Step    Data    result  is a test for   status  ...
    PROJ-1  test1   des         1       step1   data1   result1 key1, key2      open    ...
    PROJ-2  test2   des         1       step1   data1   result1 key3            open    ...
                                2       step2   data2   result2                 block   ...
    PROJ-3  test3   des         1       step1   data1   result1                 resolved...
    """
    workbook = xlsxwriter.Workbook(file)
    worksheet = workbook.add_worksheet(u"issues")
    worksheet.set_column(0, 0, 18)
    worksheet.set_column(1, 1, 20)
    worksheet.set_column(2, 2, 10)
    worksheet.set_column(3, 20, 15)
    jiraUrl = url + "browse/"

    #Make sure key is always on the 1st column
    if exportTestSteps:
        headings = ["key", "summary", "orderid", "step", "data", "result"]
    else:
        headings = ["key", "summary"]
    if "key" in fields:
        fields.remove("key")
    if "summary" in fields:
        fields.remove("summary")
    headings.extend(fields)
    worksheet.write_row("A1", headings)
    row = 1
    for test in tests:
        worksheet.write_url(row, 0, jiraUrl+test["key"], string=test["key"])
        worksheet.write(row, 1, test["summary"])
        for col in range(len(headings) - len(fields), len(headings)):
            worksheet.write(row, col, test[headings[col]])
        if exportTestSteps and "test steps" in test:
            for teststep in test["test steps"]:
                worksheet.write(row, 2, teststep["orderid"])
                worksheet.write(row, 3, teststep["step"])
                worksheet.write(row, 4, teststep["data"])
                worksheet.write(row, 5, teststep["result"])
                row += 1
        else:
            row += 1
    worksheet.add_table(0, 0, row-1, len(headings)-1, {'style': 'Table Style Medium 11', 'columns': [{'header': item} for item in headings]})
    workbook.close()

def WriteTestsToCSV(file, tests, fields, url, exportTestSteps, addTitle):
    """
    write JSON test data to a .csv file
    :params file: the output file of test cases
    :params tests: the JSON data of test cases
    The csv format:
    Name    Desription  OrderId Step    Data    is a test for   status  ...
    test1   des         1       step1   data1   key1, key2      open    ...
    test2   des         1       step1   data1   key3            open    ...
                        2       step2   data2                   block   ...
    test3   des         1       step1   data1                   resolved...
    """
    f = open(file, 'w')
    jiraUrl = url + "browse/"

    headings = ["key", "summary"]
    if "key" in fields:
        fields.remove("key")
    if "summary" in fields:
        fields.remove("summary")
    headings.extend(fields)
    if addTitle:
        f.writelines('key,summary')
        if exportTestSteps:
            f.writelines(',orderid,step,data,result')
        for index in range(2, len(headings)):
            f.writelines(','+headings[index])
        f.writelines('\n')
    for test in tests:
        f.writelines(test["key"]+','+test["summary"])
        if exportTestSteps:
            if "test steps" in test:
                teststeps = test["test steps"]
                f.writelines(','+str(teststeps[0]["orderid"]))
                f.writelines(','+teststeps[0]["step"].replace('\n',' / '))
                f.writelines(','+teststeps[0]["data"].replace('\n',' / '))
                f.writelines(','+teststeps[0]["result"].replace('\n',' / '))
            else:
                f.writelines(',,,,')
        for col in range(2, len(headings)-1):
            f.writelines(','+test[headings[col]].replace(',','/'))
        if len(headings) > 2:
            f.writelines(test[headings[len(headings)-1]].replace(',','/')+'\n')
        else:
            f.writelines('\n')
        if exportTestSteps and "test steps" in test:
            teststeps = test["test steps"]
            for index in range(1, len(test["test steps"])):
                f.writelines(',,'+str(teststeps[index]["orderid"]))
                f.writelines(','+teststeps[index]["step"].replace('\n',' / '))
                f.writelines(','+teststeps[index]["data"].replace('\n',' / '))
                f.writelines(','+teststeps[index]["result"].replace('\n',' / ')+'\n')
    f.close()

def MaintainIssueLinks(args, zapi, tests, jiraIssues):
    """
    maintain linkages between issues
    :params args: command arguments
    :params zapi: ZAPI instance
    :params tests: tests from input sheet
    :params jiraIssues: the dictionary of the JIRA issues by summary
    :params linkType: the link type to maintain
    """
    #Link types are defined by JIRA API
    #https://jira.devtools.intel.com:443/rest/api/2/issueLinkType
    linkTypeMapping = {
        'is tested by' : ('Testing', 'inwardIssue'),
        'is a test for' : ('Testing', 'outwardIssue'),
        'duplicates' : ('Duplicate', 'outwardIssue'),
        'is duplicated by' : ('Duplicate', 'inwardIssue'),
        'blocks' : ('Blocks', 'outwardIssue'),
        'is blocked by':('Blocks', 'inwardIssue'),
        'clones' : ('Cloners', 'outwardIssue'),
        'is cloned by' : ('Cloners', 'inwardIssue')
        }
    for test in tests:
        summary = test['summary']
        #may need to check --updatelatest
        issueKey = jiraIssues[summary]['key']
        #get all issue links
        jql = "project = " + args.project + " AND key = " + issueKey
        testcases = zapi.executeJqlSearch(jql, "summary,description,issuelinks")
        existingIssueLinks = testcases[0]['fields']['issuelinks']
        for linkType in linkTypeMapping:
            (linkName, linkIssueType) = linkTypeMapping[linkType]
            if linkType in test:
                existingIssues = {}
                for issueLink in existingIssueLinks:
                    if linkName == issueLink['type']['name'] and linkIssueType in issueLink:
                        logging.debug("%s %s of %s, link id %s" % (issueKey, linkType, issueLink[linkIssueType]['key'], issueLink['id']))
                        existingIssues[issueLink[linkIssueType]['key']] = issueLink['id']
                inputIssues = test[linkType]
                if inputIssues <> '':
                    logging.debug("Input issues: %s" % inputIssues)
                    zapi.updateIssueLinks(issueKey, inputIssues, existingIssues, linkName, linkType, linkIssueType, args.updateLink)

def convertToJiraJson(values, property):
    '''
    convert a list to Jira JSON format
    not used for now
    '''
    JiraJson = []
    for value in values:
        JiraJson.append({property:str(value)})
    return JiraJson

def delete(args, zapi, projectConfig):
    '''
    delete a test cycle or a group of test issues from JIRA.
    '''
    if args.type == "cycle" and args.zql:
        cycleId = -1
        (issueProject, projectId, fixVersion, versionId, cycleName, cycleId) = conf.GetCycleInfo(args.zql,zapi)
        logging.info("Start to delete %s" % args.type)
        if cycleId == -1:
            logging.error("Test cycle %s does not exist, please verify." % cycleName)
            sys.exit(1)
        else:
            zapi.deleteCycle(cycleId)
            logging.info("Test cycle %s is deleted." % cycleName)
    elif args.type == "test" and args.jql:
        logging.info("Start to delete %s" % args.type)
        issues = zapi.executeJqlSearch(args.jql)
        keys = []
        for issue in issues:
            keys.append(issue["key"])
        logging.info("%d test issues will be deleted." % len(keys))
        zapi.deleteIssues(keys)
        logging.info("Test issues are deleted.")
    else:
        logging.error("Please specify the type to delete with a correspoding filter")
        sys.exit(1)
    return

def UpdateExecution(args, zapi, existingIssues, newIssues, tests):
    logging.info("Setting up environment for updating execution status...")
    executionKeys = []
    executionIds = {}
    logging.info("Checking test cycle...")
    (issueProject, projectId, fixVersion, versionId, cycleName, cycleId) = conf.SetupCycle(args,zapi)
    for (issue, test) in existingIssues:
        executionKeys.append(issue["key"])
    for newIssue in newIssues:
        executionKeys.append(newIssue["key"])
    logging.info("Adding test issues to the test cycle...")
    zapi.addTestsToCycle(executionKeys, cycleId, projectId, versionId)
    expectedExecutionCount = len(executionKeys)
    logging.debug("Expected execution count after adding tests to the test cycle: %d" % expectedExecutionCount)
    if len(executionKeys) > 0:
        logging.info("Retrieving executions from the test cycle...")
        executions = zapi.executeSearchWithExpectedCount(args.zql, expectedExecutionCount)
        if executions:
            for execution in executions:
                executionIds[execution['issueSummary']] = execution['id']
    logging.info("Updating execution status...")
    zapi.updateExecutionStatusBySlicer(tests, executionIds)
    return

def ConstructNewIssues(project, newTests):
    '''
    Prepare the json data of the new tests
    '''
    logging.info("Creating new tests...")
    issues = []
    for test in newTests:
        issue = ConstructIssueInfo(test, "create", project)
        issues.append({"fields": issue})
    return issues

def GetJiraIssues(zapi, jql):
    """
    Retrieve test issues from JIRA project by JQL
    :params zapi: ZAPI instance
    :params jql: JQL statement for the query
    :return: issue by summary
    """
    issues = []
    jiraIssues = {}

    #extra check needed to ensure all test cases are pulled out?
    issues = zapi.executeJqlSearch(jql)
    duplicateTestCountInTotal = 0
    for issue in issues:
        summary = issue["fields"]["summary"]
        if summary not in jiraIssues:
            jiraIssues[summary] = issue
            jiraIssues[summary]["count"] = 1
        else:
            jiraIssues[summary]["count"] += 1
            duplicateTestCountInTotal += 1
    logging.info("Total test issues in this project: %d" % len(issues))
    logging.info("Unique test issues in this project: %d" % len(jiraIssues))
    logging.info("Duplicate test issues in this project: %d" % duplicateTestCountInTotal)
    return jiraIssues

def UpdateIssues(zapi, existingIssues, skipStepUpdate):
    """
    Update test cases and test steps
    :params zapi: ZAPI instance
    :params existingIssues: identified existing issue set
    :params skipStepUpdate: skip step update or not
    """
    #Update existing test cases one by one as no bulk operation API is provided
    #If duplicate issues in JIRA, there might be some potential issues, to be investigated
    logging.info("Updating tests...")
    for (issue, test) in existingIssues:
        #Update issue fields if any changes
        #The following is not enough to decide whether or not to update a JIRA, if more fields are introduced
        #Reuse ParseJiraSearchResult, and do comparison in a separate method
        #If users want to remove the value of a field, it won't work as it considers blank as no update
        #Improvement to be done later
        #str(test["description"]) == str(issue["fields"]["description"])
        if ("description" not in test or len(test["description"]) == 0) and \
            ("affects versions"  not in test or len(test["affects versions"]) == 0) and \
            ("fix versions" not in test or len(test["fix versions"]) == 0) and \
            ("issue viewers" not in test or len(test["issue viewers"]) == 0) and \
            ("assignee" not in test or len(test["assignee"]) == 0) and \
            ("components" not in test or len(test["components"]) == 0) and \
            ("operating systems" not in test or len(test["operating systems"]) == 0) and \
            ("acceptance criteria" not in test or len(test["acceptance criteria"]) == 0) and \
            ("labels" not in test or len(test["labels"]) == 0):
            updateTest = False
        else:
            updateTest = True

        if not updateTest:
            pass
        else:
            data = ConstructIssueInfo(test, "update")
            zapi.editIssue(issue["key"], json.dumps(data))

        #Update test steps
        #1. Get test steps by test id
        #2. Compare the test steps between Zephyr and Input file
        #3. Delete test steps by test step id
        #4. Create test steps
        if not skipStepUpdate:
            teststeps = zapi.getTestSteps(issue["id"])
            if len(teststeps) == 0:
                if "teststeps" in test:
                    zapi.createTestSteps(issue["id"], test["teststeps"])
            else:
                #Extract basic information from teststeps
                extracted_teststeps = []
                teststepId_dict = {}
                for teststep in teststeps:
                    extracted_teststep = {}
                    extracted_teststep["orderid"] = teststep["orderId"]
                    extracted_teststep["step"] = teststep["step"]
                    extracted_teststep["data"] = teststep["data"]
                    extracted_teststep["result"] = teststep["result"]
                    extracted_teststeps.append(extracted_teststep)
                    teststepId_dict[teststep["orderId"]] = teststep["id"]
                #Compare and update the steps that exist on both sides
                extracted_teststeps.sort()
                input_teststeps = []
                if "teststeps" in test:
                    for teststep in test["teststeps"]:
                        input_teststep = {}
                        if "orderid" in teststep:
                            input_teststep["orderid"] = teststep["orderid"]
                        if "step" in teststep:
                            input_teststep["step"] = teststep["step"]
                        if "data" in teststep:
                            input_teststep["data"] = teststep["data"]
                        if "result" in teststep:
                            input_teststep["result"] = teststep["result"]
                        input_teststeps.append(input_teststep)
                    input_teststeps.sort()
                for zephyr_teststep, input_teststep in zip(extracted_teststeps, input_teststeps):
                    if cmp(zephyr_teststep, input_teststep) <> 0:
                        zapi.updateTestStep(issue["id"], teststepId_dict[zephyr_teststep["orderid"]], input_teststep)
                        logging.debug("%s: updated step %d" % (issue["key"], zephyr_teststep["orderid"]))
                #If the counts of test steps don't match, then create or delete test steps
                lenZephyr = len(extracted_teststeps)
                lenInput = len(input_teststeps)
                i = 0
                if lenZephyr < lenInput:
                    while lenZephyr + i < lenInput:
                        zapi.createTestStep(issue["id"], input_teststeps[lenZephyr + i])
                        logging.debug("%s: create one step" % issue["key"])
                        i += 1
                elif lenZephyr > lenInput:
                    while lenZephyr > lenInput + i:
                        zapi.deleteTestStep(issue["id"], teststepId_dict[extracted_teststeps[lenInput + i]["orderid"]])
                        logging.debug("%s: deleted step %d" % (issue["key"], extracted_teststeps[lenInput + i]["orderid"]))
                        i += 1

def ConstructIssueInfo(test, action, project=None):
    """
    Construct issue info for JIRA update based on test
    :params test: test case information
    :params action: create or update an issue
    :return: Issue info as defined by JIRA
    """
    data = {}
    fields = {}
    fields["summary"] = test["summary"]
    if "description" in test and len(test["description"]) > 0:
        fields["description"] = test["description"]
    if "affects versions" in test and len(test["affects versions"]) > 0:
        fields["versions"] = [({"name":str(value)}) for value in test["affects versions"]]
    if "fix versions" in test and len(test["fix versions"]) > 0:
        fields["fixVersions"] = [({"name":str(value)}) for value in test["fix versions"]]
    if "issue viewers" in test and len(test["issue viewers"]) > 0:
        fields["customfield_15005"] = [({"name":str(value)}) for value in test["issue viewers"]]
    if "assignee" in test and len(test["assignee"]) > 0:
        fields["assignee"] = {"name":str(test["assignee"])}
    if "components" in test and len(test["components"]) > 0:
        fields["components"] = [({"name":str(value)}) for value in test["components"]]
    if "operating systems" in test and len(test["operating systems"]) > 0:
        fields["customfield_11119"] = [({"value":str(value)}) for value in test["operating systems"]]
    if "acceptance criteria" in test and len(test["acceptance criteria"]) > 0:
        fields["customfield_11609"] = str(test["acceptance criteria"])
    if "labels" in test and len(test["labels"]) > 0:
        fields["labels"] = test["labels"].split(",")
    #"environment":str(test["environment"]),
    #"customfield_11700": [{"value":str(test["classification"])}],
    #"customfield_11609": str(test["acceptance criteria"])
    if action == "update":
        data = {
            "fields" : fields
        }
    elif action == "create":
        data = {
            "project": {
                "key": project
            },
            "issuetype": {
                "name": "Test"
            }
        }
        data.update(fields)
    return data

def IdentifyTestSets(tests, jiraIssues, updateLatest):
    """
    identify test sets for JIRA update
    :params tests: test information
    :params jiraIssues: JIRA issue by summary
    :params updateLatest: update the latest record if any duplicates
    :return: existing issue set, new test set and new test step set
    """
    existingIssues = []
    newTests = []
    duplicateIssueCount = 0

    for test in tests:
        summary = test['summary']
        if summary in jiraIssues:
            issueCount = jiraIssues[summary]["count"]
            issue = jiraIssues[summary]
            if issueCount > 1:
                duplicateIssueCount += 1
                if not updateLatest:
                    continue
                else:
                    #Always use the latest key to update if multiple entries exist
                    existingIssues.append((issue, test))
            elif issueCount == 1:
                existingIssues.append((issue, test))
        else:
            newTests.append(test)

    if duplicateIssueCount > 0:
        if not updateLatest:
            logging.warn('%d tests matching duplicate issues in JIRA are ignored.' % duplicateIssueCount)
        else:
            logging.info('%d tests matching duplicate issues in JIRA.' % duplicateIssueCount)
    return (existingIssues, newTests)

def CreateTestSteps(zapi, newIssues, jiraIssues, newTests):
    """
    Create new steps for new issues
    :params zapi: ZAPI instance
    :params newIssues: new test cases
    :params jiraIssues: dictionary of JIRA issue by summary
    :params newTests: dictionary of new tests
    """
    issueSummaryByKey = {jiraIssues[summary]["key"] : summary for summary in jiraIssues}
    newTestBySummary = {test["summary"] : test for test in newTests}
    for newIssue in newIssues:
        testSteps = {}
        if newIssue["key"] in issueSummaryByKey:
            summary = issueSummaryByKey[newIssue["key"]]
            if summary in newTestBySummary and "teststeps" in newTestBySummary[summary]:
                testSteps = newTestBySummary[summary]["teststeps"]
                zapi.createTestSteps(newIssue["id"], testSteps)

def UpdateComment(zapi, tests, jiraIssues):
    """
    Update commentsfor issues
    :params zapi: ZAPI instance
    :params tests: new test cases
    :params jiraIssues: dictionary of JIRA issues by summary
    """
    for test in tests:
        key = jiraIssues[test["summary"]]["key"]
        if test["summary"] in jiraIssues:
            if "comment" in test and len(test["comment"]) > 0:
                    zapi.addComment(key, test["comment"])
            if "teststepSummary" in test and len(test["teststepSummary"]) > 0:
                    zapi.addComment(key, test["teststepSummary"])

def verifyZQLParser(args, zapi, projectConfig):
    '''
    verify the ZQL parser in the conf.py scripts.
    '''
    tests_ZQL = [
        {"zql" : "project = 'EETRACEBIM' AND fixVersion = 'VER1' AND cycleName in ('demo_for_verify')",
         "expected result" : {"project" : "EETRACEBIM", "fixVersion" : "VER1", "cycleName" : "demo_for_verify"},
         "caseId" : "test1001"
         },
        {"zql" : "project = 'EETRACEBIM' AND fixVersion = 'VER1 (Beta)' AND cycleName in ('demo_for_verify')",
         "expected result" : {"project" : "EETRACEBIM", "fixVersion" : "VER1 (Beta)", "cycleName" : "demo_for_verify"},
         "caseId" : "test1002"
         },
        {"zql" : "project = 'EETRACEBIM' AND fixVersion = 'ww03\\'19' AND cycleName in ('demo_for_verify')",
         "expected result" : {"project" : "EETRACEBIM", "fixVersion" : "ww03'19", "cycleName" : "demo_for_verify"},
         "caseId" : "test1003"
         },
        {"zql" : "project = \"EETRACEBIM\" AND fixVersion = \"VER1\" AND cycleName in (\"demo_for_verify\")",
         "expected result" : {"project" : "EETRACEBIM", "fixVersion" : "VER1", "cycleName" : "demo_for_verify"},
         "caseId" : "test1004"
         },
        {"zql" : "project = \"EETRACEBIM\" AND fixVersion = \"VER1 (Beta)\" AND cycleName in (\"demo_for_verify\")",
         "expected result" : {"project" : "EETRACEBIM", "fixVersion" : "VER1 (Beta)", "cycleName" : "demo_for_verify"},
         "caseId" : "test1005"
         },
        {"zql" : "project = \"EETRACEBIM\" AND fixVersion = \"ww03\\'19\" AND cycleName in (\"demo_for_verify\")",
         "expected result" : {"project" : "EETRACEBIM", "fixVersion" : "ww03'19", "cycleName" : "demo_for_verify"},
         "caseId" : "test1006"
         },
        {"zql" : "project = EETRACEBIM AND fixVersion = 'ww03\\'19 2019' AND cycleName in (\"demo_for_verify (Beta) 测试')",
         "expected result" : {"project" : "EETRACEBIM", "fixVersion" : "ww03'19 2019", "cycleName" : "demo_for_verify (Beta) 测试"},
         "caseId" : "test1007"
         },
        {"zql" : "project = \"EETRACE\\'BIM\" AND fixVersion = \"ww03\\'19\" AND cycleName in (\"demo_for_verify ww03\\'19\")",
         "expected result" : {"project" : "EETRACE'BIM", "fixVersion" : "ww03'19", "cycleName" : "demo_for_verify ww03'19"},
         "caseId" : "test1008"
         },
        {"zql" : "project = \"EETRACE\\\"BIM\" AND fixVersion = \"ww03\\\"19\" AND cycleName in (\"demo_for_verify ww03\\\"19\")",
         "expected result" : {"project" : "EETRACE\"BIM", "fixVersion" : "ww03\"19", "cycleName" : "demo_for_verify ww03\"19"},
         "caseId" : "test1009"
         }
        ]


    tests_separate_options = [
        {"input" : {"project" : "'EETRACEBIM'", "fixVersion" : "'VER1'", "cycleName" : "'demo_for_verify'"},
         "expected result" : {"project" : "EETRACEBIM", "fixVersion" : "VER1", "cycleName" : "demo_for_verify"},
         "caseId" : "test2001"
         },
        {"input" : {"project" : "'EETRACEBIM'", "fixVersion" : "'VER1 (Beta)'", "cycleName" : "'demo_for_verify'"},
         "expected result" : {"project" : "EETRACEBIM", "fixVersion" : "VER1 (Beta)", "cycleName" : "demo_for_verify"},
         "caseId" : "test2002"
         },
        {"input" : {"project" : "'EETRACEBIM'", "fixVersion" : "'ww03\\\'19'", "cycleName" : "'demo_for_verify'"},
         "expected result" : {"project" : "EETRACEBIM", "fixVersion" : "ww03'19", "cycleName" : "demo_for_verify"},
         "caseId" : "test2003"
         },
        {"input" : {"project" : "\"EETRACEBIM\"", "fixVersion" : "\"VER1\"", "cycleName" : "\"demo_for_verify\""},
         "expected result" : {"project" : "EETRACEBIM", "fixVersion" : "VER1", "cycleName" : "demo_for_verify"},
         "caseId" : "test2004"
         },
        {"input" : {"project" : "\"EETRACEBIM\"", "fixVersion" : "\"VER1 (Beta)\"", "cycleName" : "\"demo_for_verify\""},
         "expected result" : {"project" : "EETRACEBIM", "fixVersion" : "VER1 (Beta)", "cycleName" : "demo_for_verify"},
         "caseId" : "test2005"
         },
        {"input" : {"project" : "\"EETRACEBIM\"", "fixVersion" : "\"ww03\\\'19\"", "cycleName" : "\"demo_for_verify\""},
         "expected result" : {"project" : "EETRACEBIM", "fixVersion" : "ww03'19", "cycleName" : "demo_for_verify"},
         "caseId" : "test2006"
         },
        {"input" : {"project" : "EETRACEBIM", "fixVersion" : "ww03\\\'19 2019", "cycleName" : "demo_for_verify (Beta) 测试"},
         "expected result" : {"project" : "EETRACEBIM", "fixVersion" : "ww03'19 2019", "cycleName" : "demo_for_verify (Beta) 测试"},
         "caseId" : "test2007"
         },
        {"input" : {"project" : "EETRACE\\\'BIM", "fixVersion" : "ww03\\\'19", "cycleName" : "demo_for_verify ww03\\\'19"},
         "expected result" : {"project" : "EETRACE'BIM", "fixVersion" : "ww03'19", "cycleName" : "demo_for_verify ww03'19"},
         "caseId" : "test2008"
         },
        {"input" : {"project" : "EETRACE\\\"BIM", "fixVersion" : "ww03\\\"19", "cycleName" : "demo_for_verify ww03\\\"19"},
         "expected result" : {"project" : "EETRACE\"BIM", "fixVersion" : "ww03\"19", "cycleName" : "demo_for_verify ww03\"19"},
         "caseId" : "test2009"
         }
        ]

    tests = tests_ZQL + tests_separate_options

    for test in tests:
        if "zql" not in test:
            zql = 'project = ' + conf.addQuote(test["input"]["project"]) + ' and ' + \
                'fixVersion = ' + conf.addQuote(test["input"]["fixVersion"]) + ' and ' + \
                'cycleName in (' + conf.addQuote(test["input"]["cycleName"]) + ')'
        else:
            zql = test["zql"]
        logging.debug("Executing test (caseID: %s): '%s'" % (test["caseId"], zql))
        data = conf.parse_ZQL(zql)
        if cmp(data, test["expected result"]) <> 0:
            logging.error("ZQL Parser failed to parse ZQL query (caseID: %s): '%s'" % (test["caseId"], zql))
            logging.error("expected result: '%s'" % test["expected result"])
            logging.error("actual result: '%s'" % data)
            sys.exit(1)

    logging.info("ZQL Parser passes all tests.")
    return

if __name__ == '__main__':
    main()
