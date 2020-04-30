# -*- coding: utf-8 -*
#!/usr/bin/env python
'''
A class for calling restful APIs of JIRA/Zephyr.
'''
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import re
import logging
import time
from json import dumps
from base64 import b64encode
from requests.adapters import HTTPAdapter
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
from collections import defaultdict

class ZAPI(object):

    def __init__(self, url, username=None, password=None, disableSSL=None, cert=None, \
        maxRetry=30, timeout=10, timeToAddATest=4, slicerToAddTests=50, slicerToUpdateExecutions=1000):
        '''
        Initialize the class by JIRA url and user/password.
        '''
        self.baseURL = url.rstrip('/')
        self.headers = None
        if username is not None and password is not None:
            self.headers = {"Authorization": "Basic " + b64encode(
                username + ":" + password), "Content-Type": "application/json"}
        self.session = requests.Session()
        if disableSSL:
            self.session.verify = False
        elif cert:
            self.session.verify = cert
        self.validateInput(maxRetry, timeout, timeToAddATest, slicerToAddTests, slicerToUpdateExecutions)
        self.session.keep_alive = False
        self.session.get(self.baseURL)
        self.session.mount('https://',HTTPAdapter(max_retries=self.maxRetry))
        self.session.mount('http://',HTTPAdapter(max_retries=self.maxRetry))

    def validateInput(self, maxRetry=30, timeout=10, timeToAddATest=4, slicerToAddTests=50, slicerToUpdateExecutions=1000):
        """
        Create new JIRA Test issues in specified project
        :params maxRetry: max retry count for the same API call
        :params timeout: time interval between API calls
        :params timeToAddATest: average Time to add a test to a test cycle
        :params slicerToAddTests: test count to add tests to a test cycle by groups
        :params slicerToUpdateExecutions: Execution count to update status to a test cycle by groups
        :returns: test keys, ids or list of issues
        """
        #Input validation
        if maxRetry < 5:
            maxRetry = 5
        elif maxRetry > 300:
            maxRetry = 300
        self.maxRetry = maxRetry

        if timeout < 1:
            timeout = 1
        elif timeout > 50:
            timeout = 50
        self.timeout = timeout

        if timeToAddATest < 0.1:
            timeToAddATest = 0.1
        elif timeToAddATest > 10:
            timeToAddATest = 10
        self.timeToAddATest = timeToAddATest

        if slicerToAddTests < 20:
            slicerToAddTests = 20
        elif slicerToAddTests > 500:
            slicerToAddTests = 500
        self.slicerToAddTests = slicerToAddTests

        if slicerToUpdateExecutions < 200:
            slicerToUpdateExecutions = 200
        elif slicerToUpdateExecutions > 2000:
            slicerToUpdateExecutions = 2000
        self.slicerToUpdateExecutions = slicerToUpdateExecutions

    def createTestIssues(self, issues, result='key', slicer=20):
        """
        Create new JIRA Test issues in specified project
        :params issues: dict type of test data, data detail from /rest/api/2/issues/createmeta
        :params result: return keys by default, or ids, or a list of issues
        :params slicer: during bulk upload, user can choose the number of issues to upload per API call, if too big it might raise connection timeout
        :returns: test keys, ids or list of issues
        """
        count = len(issues)
        i = 0
        maxRetry = self.maxRetry
        newTestsKey = []
        newTestsId = []
        newTests = []

        logging.info("Processing to create %d issues" % count)
        #No similar jobProgress found in JIRA Restful API, so split the work to notify user on the progress
        while i < count:
            if i + slicer -1 >= count:
                j = count
            else:
                j = i + slicer
            data = dumps({"issueUpdates": issues[i:j]})
            res = self.session.post(self.baseURL + "/rest/api/2/issue/bulk/", data=data, headers=self.headers)
            if res.ok:
                #bug to be fixed, for mulitiple records, the server returns 201 OK even if few records fail
                #script shall stop and report errors
                logging.info("%d Test Issues Created!" % (j - i))
                for issue in res.json()["issues"]:
                    newTestsKey.append(issue["key"])
                    newTestsId.append(issue["id"])
                newTests.extend(res.json()["issues"])
                i += slicer
            else:
                logging.info(("Failed to create test issues! " + 
                             "Server returns status code: %d. " +
                             "Sleep %ds and retry.") % (res.status_code, self.timeout))
                time.sleep(self.timeout)
                if maxRetry == 0:
                    logging.error("Retried for %d times, the server is not responding or failing." % self.maxRetry)
                    if "errorMessages" in res.json():
                        logging.error(res.json()["errorMessages"])
                    if "errors" in res.json():
                        logging.error(res.json()["errors"])
                    sys.exit(1)
                maxRetry -= 1
        if result == 'key':
            return newTestsKey
        elif result == 'id':
            return newTestsId
        elif result == 'issue':
            return newTests

    def executeJqlSearch(self, jqlText, fields = "summary"):
        """
        Get ticket list by jql
        :params jqlText: jira query language, string
        :params fields: expected fields in return value
        :returns: ticket data, list of json
        """
        total = 0
        start = 0
        issues = []
        jql = jqlText + ' ORDER BY key ASC'
        res = self.session.get(
            self.baseURL + '/rest/api/2/search?fields=' + fields + '&maxResults=1&jql=' + jql, headers=self.headers)
        if res.ok:
            js_data = res.json()
            total = js_data['total']
            time.sleep(self.timeout)

        while total > 0:
            total -= 1000
            res = self.session.get(
                self.baseURL + '/rest/api/2/search?fields=' + fields + '&startAt=' + str(start) + '&maxResults=1000&jql=' + jql, headers=self.headers)
            if res.ok:
                js_data = res.json()
                if 'issues' not in js_data:
                    logging.warn(js_data['msg'])
                else:
                    for issue in js_data['issues']:
                        issues.append(issue)
                start += 1000
                time.sleep(self.timeout)
            else:
                self.reportErrorAndExit(res, "Failed to execute JQL search!")
        return issues

    def executeSearchWithExpectedCount(self, zqlQuery=None, expectedCount=0):
        '''
        Execute search for zql with an exepcted target count, this is to ensure
         to get correct and full results as sometimes JIRA returns earlier 
        before all executions are added, even which is complete as indicated by
        jobprogress.
        :params zqlQuery: ZQL Query, string
        :params expectedCount: exepected execution count, integer
        :returns: list of json
        '''
        #bug need mechanism to stop the retry if it cannot match the expectedCount
        totalCount = 0
        totalExecutions = []
        offset = 0
        #If expectedCount is 0, then get the total count of existing executions from the cycle
        if expectedCount == 0:
            (executions, totalCount) = self.executeSearch(zqlQuery, 0, 1)
            logging.debug("Length of expected executions %d" % expectedCount)
            logging.debug("Length of actual executions %d" % totalCount)
            logging.debug("Sleep %ds for system to complete last operation" % self.timeout)
            time.sleep(self.timeout)
            expectedCount = totalCount

        #Quick query to compare the expected count and the total count of executions from the cycle
        #This is a workaround to avoid the case when tests are added, the job status is complete but some executions are not there yet
        maxRetry = self.maxRetry
        while (expectedCount != totalCount):
            (executions, totalCount) = self.executeSearch(zqlQuery, 0, 1)
            logging.debug("Length of expected executions %d" % expectedCount)
            logging.debug("Length of actual executions %d" % totalCount)
            logging.debug("Sleep %ds for system to complete last operation" % self.timeout)
            time.sleep(self.timeout)
            maxRetry -= 1
            if maxRetry == 0:
                logging.error("Exits after reaching maximum %d retries." % (self.maxRetry))
                sys.exit(1)

        #Retrieve the executions by offset
        #Test run to estimate how many API calls required to pull out executions
        (executions, totalCount) = self.executeSearch(zqlQuery, offset)
        if len(executions) != 0:
            estimateAPICalls = int(totalCount/len(executions)) + 1
        else:
            estimateAPICalls = 0
        maxRetry = self.maxRetry + estimateAPICalls
        while len(totalExecutions) < expectedCount:
            (executions, totalCount) = self.executeSearch(zqlQuery, offset)
            offset += len(executions)
            totalExecutions.extend(executions)
            logging.debug("Sleep %ds for system to complete last operation" % self.timeout)
            time.sleep(self.timeout)
            maxRetry -= 1
            if maxRetry == 0:
                logging.error("Exits after reaching maximum %d retries." % (self.maxRetry + estimateAPICalls))
                sys.exit(1)

        return totalExecutions

    def executeSearch(self, zqlQuery=None, offset=0, maxRecord=998):
        """
        Execute search for zql
        :params zqlQuery: ZQL Query, string
        :params offset: offset of this query
        :params maxRecord: maximum executions returned as defined by IT
        :returns: list of json, total count
        """
        logging.debug("Executing ZQL Query: %s" % zqlQuery)
        if zqlQuery is not None:
            res = self.session.get(
                self.baseURL + "/rest/zapi/latest/zql/executeSearch?maxRecords=" + str(maxRecord) + "&offset=" + str(offset) \
                    , params=dict(zqlQuery=zqlQuery), headers=self.headers)
        objResponse = res.json()
        if res.ok:
            if "totalCount" not in objResponse:
                return (objResponse["executions"], 0)
            else:
                return (objResponse["executions"], objResponse["totalCount"])
        else:
            self.reportErrorAndExit(res, "Failed to execute ZQL search!")

    def getExecutionListFromCycle(self, cycleId):
        """
        get an execution list from a cycle
        :params cycleId: cycle Id
        :returns: a dict of issue key and execution Id
        """
        executionDict = {}
        executions = []
        res = self.session.get(
            self.baseURL + "/rest/zapi/latest/execution?cycleId=" + cycleId, headers=self.headers)
        if res.ok:
            executions = res.json()["executions"]
            for execution in executions:
                executionDict[execution["issueKey"]] = execution["id"]
            return executionDict
        else:
            return executionDict

    def updateBulkStatus(self, Id, statusId):
        """
        update execution status
        :params id: execution Id
        :params statusId: status Id, 1: PASS, 2: FAIL
        :returns: status_code
        """
        if isinstance(Id, list):
            data = dumps({
               "executions": Id, "status": str(statusId), "comment": "test", "htmlComment": "html test", "summary": "summary", "assignedTo": "wmao2"
            })
            res = self.session.put(self.baseURL + "/rest/zapi/latest/execution/updateBulkStatus",
                data=data, headers=self.headers)
        else:
            data = dumps({
            "status": str(statusId)
            })
            res = self.session.put(self.baseURL + "/rest/zapi/latest/execution/" + str(
                Id) + "/execute", data=data, headers=self.headers)
        return res.status_code

    def listCycles(self, projectId, cycleName, versionId=None, version=None):
        """
        search cycle based on project id and cycle name
        :params projectId: project id
        :params cycleName: cycle name
        :params versionId: project version id
        :params version: project version
        :returns: a tuple of cycle id and version id
        """
        url = self.baseURL + \
            '/rest/zapi/latest/cycle?projectId=' + str(projectId)
        if versionId is not None:
            url += '&versionId=%s' % str(versionId)
        res = self.session.get(url, headers=self.headers)
        js_data = res.json()
        cycles = []
        if versionId is not None:
            for _cycleId, cycle_info in js_data.items():
                if isinstance(cycle_info, dict):
                    if cycle_info['name'] == cycleName:
                        cycles.append((_cycleId, versionId))
        else:
            for _, cycle_list in js_data.items():
                for cycle in cycle_list:
                    for _cycleId, cycle_info in cycle.items():
                        if isinstance(cycle_info, dict):
                            if version is None:
                                if cycle_info['name'] == cycleName:
                                    cycles.append((_cycleId, cycle_info['versionId']))
                            else:
                                if cycle_info['name'] == cycleName and cycle_info['versionName'] == version:
                                    cycles.append((_cycleId, cycle_info['versionId']))
        if len(cycles) > 1:
            logging.error('Multiple cycles found for cycle Name: %s, and you must specifiy project version or check if duplicate cycle names under the same version' % cycleName)
            logging.error('%s' % cycles)
            sys.exit(1)
        elif len(cycles) == 0:
            logging.debug('Cycle %s does not exist.' % cycleName)
            return (None, None)
        else:
            return cycles[0]

    def createNewCycle(self, projectId, cycleName, versionId=None, startDate=None, endDate=None, build=None, environment=None, description=None):
        """
	    create a new Cycle
	    :params cycleName: cycle name
	    :params projectId: project Id
	    :params versionId: version Id
	    :params startDate: cycle start date
	    :params endDate: cycle end date
	    :params build: build info
	    :params environment: cycle environment
	    :params description: cycle description
	    :returns: cycle Id, string(Create cycle under unscheduled version if the versionId=-1)
	    """
        if not startDate:
            startDate = ""
        if not endDate:
            endDate = ""
        values = dumps({
	        "clonedCycleId": "",
	        "name": str(cycleName),
	        "build": str(build),
	        "environment": str(environment),
	        "description": str(description),
	        "startDate": str(startDate), #format: 12/Jun/2018
	        "endDate": str(endDate), #format: 12/Jun/2018
	        "projectId": str(projectId),
	        "versionId": str(versionId)
	    })
        res = self.session.post(
	        self.baseURL + "/rest/zapi/latest/cycle/", data=values, headers=self.headers)	
        if res.ok:
            return res.json()['id']
        else:
            self.reportErrorAndExit(res, "Failed to create a new test cycle!")

    def updateCycle(self, cycleId, versionId=None, startDate="", endDate="", build=None, environment=None, description=None):
        """
	    update a test Cycle
	    :params cycleId: cycle Id	
	    :params versionId: version Id
	    :params startDate: cycle start date
	    :params endDate: cycle end date
	    :params build: build info
	    :params environment: cycle environment
	    :params description: cycle description
	    :returns: cycle Id, string(Create cycle under unscheduled version if the versionId=-1)
	    """
        values = dumps({
	        "id": cycleId,	
	        "build": str(build),
	        "environment": str(environment),
	        "description": str(description),
	        "startDate": str(startDate), #format: 12/Jun/2018
	        "endDate": str(endDate), #format: 12/Jun/2018	
	        "versionId": str(versionId)
	    })
        res = self.session.put(
	        self.baseURL + "/rest/zapi/latest/cycle/", data=values, headers=self.headers)	
        if res.ok:
            return res.json()['id']
        else:
            self.reportErrorAndExit(res, "Failed to update a new test cycle!")

    def addTestsToCycleFromSuite(self, cycleId, fromCycleId, projectId, versionId, fromVersionId):
        """
        add tests from another cycle to a new cycle
        :params cycleId: cycle Id
        :params fromCycleId: from cycle Id
        :params projectId: project Id
        :params versionId: version id
        :params fromVersionId: version id of the suite
        :returns: string
        """
        maxRetry = self.maxRetry
        data = dumps({
            "cycleId": str(cycleId),
            "fromCycleId": str(fromCycleId),
            "fromVersionId": str(fromVersionId),
            "method": "3",
            "projectId": str(projectId),
            "versionId": str(versionId)
        })
        res = self.session.post(
            self.baseURL + "/rest/zapi/latest/execution/addTestsToCycle/", data=data, headers=self.headers)
        if res.ok:
            progress = 0
            estimateDuration = max(20, self.timeout)
            acturalDuration = 0
            while progress <> 1:
                time.sleep(estimateDuration)
                acturalDuration += estimateDuration
                progress = self.getJobProgressStatus(res.json()["jobProgressToken"], "add_tests_to_cycle_job_progress")
                estimateDuration = max(20, estimateDuration/2, self.timeout)
                maxRetry -= 1
                if maxRetry == 0:
                    logging.error("addTestsToCycle exits after reaching maximum retries with %s seconds" % (acturalDuration))
                    sys.exit(1)
            logging.debug("addTestsToCycleFromSuite Duration - estimated: %d, actual: %d" % (20, acturalDuration))
            return res.json().keys()[0]
        else:
            self.reportErrorAndExit(res, "Failed to add tests to a test cycle from another test cycle/suite!")

    def addTestsToCycle(self, issues, cycleId, projectId, versionId):
        """
        add a list of tests to a test cycle
        :params cycleId: cycle id
        :params issues: list of test ids
        :params projectId: project id
        :params versionId: version id
        :returns: string
        """
        maxRetry = self.maxRetry
        data = dumps({
            "issues": issues,
            "cycleId": str(cycleId),
            "method": "1",
            "projectId": str(projectId),
            "versionId": str(versionId)
        })
        res = self.session.post(
            self.baseURL + "/rest/zapi/latest/execution/addTestsToCycle/", data=data, headers=self.headers)
        if res.ok:
            progress = 0
            #09/06/2019: Due to server slowness, allow users to modify the estimated time to add a test
            estimateDuration = max(20, len(issues)*self.timeToAddATest, self.timeout)
            acturalDuration = 0
            while progress != 1:
                time.sleep(estimateDuration)
                acturalDuration += estimateDuration
                progress = self.getJobProgressStatus(res.json()["jobProgressToken"], "add_tests_to_cycle_job_progress")
                estimateDuration = max(20, estimateDuration/2, self.timeout)
                maxRetry -= 1
                if maxRetry == 0:
                    logging.error("addTestsToCycle exits after reaching maximum retries with %s seconds" % (acturalDuration))
                    sys.exit(1)
            logging.debug("addTestsToCycle Duration - estimated: %d, actual: %d" % (len(issues)*self.timeToAddATest, acturalDuration))
            return res.json()["jobProgressToken"]
        else:
            self.reportErrorAndExit(res, "Failed to add test cases to test cycle")

    def getJobProgressStatus(self, jobProgressToken, type):
        """
        get the status by job progress token
        :params jobProgressToken: job progress token
        :returns: status message string
        """
        res = self.session.get(
            self.baseURL + "/rest/zapi/latest/execution/jobProgress/" + str(jobProgressToken) + "?type=" + type, headers=self.headers)
        if res.ok:
            #Bug: 8/29/2018: no json returned - if this job is complete quickly, it returns NULL???
            if not res.json():
                return 0
            elif "progress" in res.json():
                return res.json()["progress"]
            else:
                return 0

    def getProjectId(self, projectKey):
        """
        get project id
        :params projectKey: project key
        :returns: projectId
        """
        res = self.session.get(
            self.baseURL + '/rest/api/2/project/' + projectKey, headers=self.headers)
        if res.ok:
            return res.json()['id']
        else:
            logging.error("Project %s doesn't exist or no permission to access." % projectKey)
            self.reportErrorAndExit(res)

    def getVersionId(self, projectKey, versionName):
        """
        get version id
        :params projectKey: project key
        :params versionName: version name
        :returns: versionId, string
        """
        res = self.session.get(
            self.baseURL + '/rest/api/2/project/' + projectKey + '/versions', headers=self.headers)
        if res.ok:
            for version in res.json():
                if version['name'] == versionName.replace("\\'","'"):
                    return version['id']
            logging.error('No such verison found: \'%s\'' % versionName)
            sys.exit(1)
        else:
            self.reportErrorAndExit(res)

    def getExecutionCountAfterMerge(self, toCycleId, fromCycleId):
        '''
        :returns: the expected execution count after clone one cycle to another
        '''
        executionOfToCycle = self.getExecutionListFromCycle(toCycleId)
        executionOfFromCycle = self.getExecutionListFromCycle(fromCycleId)
        mergedCycle = executionOfFromCycle
        #Merge two dictionaries
        executionOfToCycle.copy().update(mergedCycle)
        return len(mergedCycle)

    def getJiraField(self):
        """
        get a dictionary of all JIRA fields, both System and Custom
        :returns: a dictionary of {"field name" : "field id"}
        """
        jiraField = {}
        jiraFieldType = {}
        fields = []
        supportedDataTypes = ["key", "string", "array", "datetime", "option", \
            "user", "issuetype", "number", "date", "any", "status", "project",\
            "priority", "resolution", "progress", "securitylevel", "option-with-child"]
        unsupportedDataTypes = ["watches", "votes", "images", "timetracking", \
            "security", "comments-page", "version"]
        dataTypes = []
        dataTypes.extend(supportedDataTypes)
        dataTypes.extend(unsupportedDataTypes)
        res = self.session.get(
            self.baseURL + "/rest/api/2/field", headers=self.headers)
        if res.ok:
            fields = res.json()
            for field in fields:
                if field["name"] == "Key":
                    field["schema"] = {"type":"key"}
                if field["name"] == "Images":
                    field["schema"] = {"type":"images"}
                if "schema" not in field:
                    logging.warn("%s doesn't have an associated schema type." % field["name"])
                else:
                    if field["schema"]["type"] not in dataTypes:
                        logging.warn("%s : %s" % (field["name"], field["schema"]["type"]))
                jiraField[field["name"].lower()] = field
            return jiraField
        else:
            self.reportErrorAndExit(res, 'Failed to pull out JIRA fields')

    def reportErrorAndExit(self, res, message=None):
        """
        report server error and exit
        :params res: the response from server
        :params message: message to users
        """
        if not message:
            logging.error('%s' % message)
        try:
            if "errorMessages" in res.json():
                logging.error(res.json()["errorMessages"])
        except ValueError:
            logging.error("Cannot locate the error message from server, here is what the server returns:\n%s" % res.text)
        sys.exit(1)

    def addComment(self, issueKey, comment):
        """
        add a comment
        :params issueKey: issue key
        :params comment: new comment to add
        """
        data = dumps({
            "body": str(comment)
        })
        res = self.session.post(
            self.baseURL + "/rest/api/2/issue/" + issueKey + "/comment/", data=data, headers=self.headers)
        if not res.ok:
            logging.error("Failed to add a comment to %s!" % issueKey)
            self.reportErrorAndExit(res)

    def addTestsToCycleBySlicer(self, issues, cycleId, projectId, versionId):
        """
        add a list of tests to a test cycle by slicer
        :params cycleId: cycle id
        :params issues: list of test ids
        :params projectId: project id
        :params versionId: version id
        :returns: True
        """
        total = len(issues)
        index = 0
        slicer = self.slicerToAddTests

        while total > index:
            if total > index+slicer:
                items = issues[index:index+slicer]
            else:
                items = issues[index:total]
            self.addTestsToCycle(items, cycleId, projectId, versionId)
            index += slicer
        return True

    def updateExecutionStatus(self, tests, executionIds):
        '''
        Update the exectuion status in bulk upload
        :params tests: input tests
        :params executionIds: a dictionary of execution ids by issue summary
        '''
        #From the input file, if a test case is already part of the test cycle, get the executionId; otherwise, skip
        executionStatus = defaultdict(list)
        for test in tests:
            summary = test['summary']
            if summary in executionIds:
                executionId = executionIds[summary]
                if 'execution status' in test:
                    executionStatus[test['execution status']].append(executionId)

        #Bulk update execution status to Zephyr
        for status, executions in executionStatus.items():
            self.updateBulkStatus(executions, status)

    def updateExecutionStatusBySlicer(self, tests, executionIds):
        '''
        Update the exectuion status in bulk upload
        :params tests: input tests
        :params executionIds: a dictionary of execution ids by issue summary
        '''
        #From the input file, if a test case is already part of the test cycle, get the executionId; otherwise, skip
        total = len(tests)
        index = 0
        slicer = self.slicerToUpdateExecutions

        while total > index:
            if total > index+slicer:
                items = tests[index:index+slicer]
            else:
                items = tests[index:total]
            self.updateExecutionStatus(items, executionIds)
            index += slicer
