# -*- coding: utf-8 -*
#!/usr/bin/env python
'''
The purpose of this script is to get the specific project configuration for
processing the junit_converter.py or zephyr_zapi.py scripts.
'''
import os
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import platform
import re
import logging
from json import load

def ConfigLogging(debug=False, verbose=False):
    '''
    config the logging level
    '''
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARN
    logging.basicConfig(format='%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s', level=level)

def GetProjectConfig(configFile):
    '''
    read the project config file
    '''
    projectConfig = {}
    if configFile:
        try:
            with open(configFile, 'r') as configObj:
                projectConfig = load(configObj)
                return projectConfig
        except IOError:
            logging.error("The config file %s cannot be found." % configFile)
            sys.exit(1)
    else:
        logging.error("Please specify your project config file by --config")
        sys.exit(1)

def GetUserPassword(profile=None, projectConfig=None):
    '''
    get JIRA user name and password for calling JIRA/Zephyr APIs
    '''
    #username = os.getenv('JIRAUSER')
    #password = os.getenv('JIRAPASSWORD')
    username = "dsgirish"
    password = "Bangalore$123"
    #The follow option to read username/password from the config is disabled
    if profile and False:
        if profile in projectConfig:
            config = projectConfig[profile]
        if not username:
            logging.info("JIRAUSER env variable is not set, try to use project config")
            if 'user' in config:
                username = config['user']
        if not password:
            logging.info("JIRAPASSWORD env variable is not set, try to use project config")
            if 'password' in config:
                password = config['password']
    if not username:
        logging.error("Please specify username in environment variable JIRAUSER.")
        sys.exit(1)
    if not password:
        logging.error("Please specify password in environment variable JIRAPASSWORD.")
        sys.exit(1)
    return (username, password)

def SetupEnvironment(cert):
    systemCert = os.getenv('REQUESTS_CA_BUNDLE')
    if not systemCert:
        logging.info("Set up system cert to %s" % cert)
        os.environ['REQUESTS_CA_BUNDLE'] = cert

def GetConfigPattern(profile, projectConfig):
    '''
    parse the project config data
    :return a group of regular expression patterns
    '''
    sysstr = platform.system()
    config = None
    if profile in projectConfig:
        config = projectConfig[profile]
    else:
        logging.error("Profile %s does not exist in project config file." % profile)
        sys.exit(1)
    if(sysstr == "Windows"):
        if "logFilePattern" in config:
            logFilePattern = config["logFilePattern"]
        else:
            logging.error("Log file is required for converting test results.")
            sys.exit(1)
        if "testCasePattern" in config:
            testCasePattern = config["testCasePattern"]
        else:
            testCasePattern = ''
    elif(sysstr == "Linux"):
        if "logFilePattern" in config:
            logFilePattern = config["logFilePattern"].replace(r'\\', r'/')
        else:
            logging.error("Log file is required for converting test results.")
            sys.exit(1)
        if "testCasePattern" in config:
            testCasePattern = config["testCasePattern"].replace(r'\\', r'/')
        else:
            testCasePattern = ''
        logging.debug("logFilePattern: %s" % logFilePattern)
        logging.debug("testCasePattern: %s" % testCasePattern)
    else:
        logging.error("OS not supported")
        sys.exit(1)

    if "passPattern" in config:
        passPattern = config["passPattern"]
    if "failPattern" in config:
        failPattern = config["failPattern"]
    if "blockPattern" in config:
        blockPattern = config["blockPattern"]
    if "skipPattern" in config:
        skipPattern = config["skipPattern"]

    return (logFilePattern, testCasePattern, passPattern, failPattern, blockPattern, skipPattern)

def ApplyProjectConfigToArgs(args, projectConfig):
    config = None
    if args.profile and args.profile in projectConfig:
        config = projectConfig[args.profile]
    else:
        if sys.argv[0].find('junit_converter.py') >= 0:
            logging.error('Profile %s does not exist in the project config, please verify.' %  args.profile)
            sys.exit(1)
        else:
            logging.info('Profile %s does not exist, try to use default settings.' %  args.profile)
    if sys.argv[0].find('junit_converter.py') >= 0:
        args.outFile = MapConfigItemToArg(args.outFile, 'file', config, 'store', 'test_output.xml')
        args.log = MapConfigItemToArg(args.log, 'log', config, 'store', 'test_result')
        args.format = MapConfigItemToArg(args.format, 'format', config, 'store', 'line')
        args.encoding = MapConfigItemToArg(args.encoding, 'encoding', config, 'store', 'utf-8')
    else:
        args.url = MapConfigItemToArg(args.url, 'url', config, 'store', 'https://jira.devtools.intel.com/')
        args.cert = MapConfigItemToArg(args.cert, 'cert', config, 'store')
        args.disableSSL = MapConfigItemToArg(args.disableSSL, 'disableSSL', config, 'store_true')
        if args.command == 'execute' or args.command == 'maintenance' or  args.command == 'delete':
            jiraConfig = None
            if config and 'jiraConfig' in config:
                jiraConfig = config['jiraConfig']
            args.project = MapConfigItemToArg(args.project, 'project', jiraConfig)
            args.fixVersion = MapConfigItemToArg(args.fixVersion, 'fixVersion', jiraConfig)
            args.cycleName = MapConfigItemToArg(args.cycleName, 'cycleName', jiraConfig)
        if args.command == 'execute' or args.command == 'maintenance':
            args.newCycle = MapConfigItemToArg(args.newCycle, 'newCycle', config, 'store_true')
            args.updateLatest = MapConfigItemToArg(args.updateLatest, 'updateLatest', config, 'store_true')
            args.startDate = MapConfigItemToArg(args.startDate, 'startDate', config)
            args.endDate = MapConfigItemToArg(args.endDate, 'endDate', config)
            args.build = MapConfigItemToArg(args.build, 'build', config)
            args.environment = MapConfigItemToArg(args.environment, 'environment', config)
            args.description = MapConfigItemToArg(args.description, 'description', config)
            args.updateComment = MapConfigItemToArg(args.updateComment, 'updateComment', config, 'store_true')
        if args.command == 'execute':
            if not args.zql:
                if args.project and args.fixVersion and args.cycleName:
                    args.zql = 'project = ' + addQuote(args.project) + ' and ' + \
                        'fixVersion = ' + addQuote(args.fixVersion) + ' and ' + \
                        'cycleName in (' + addQuote(args.cycleName) + ')'
                    logging.debug('ZQL: %s' % args.zql)
                else:
                    logging.error("Please specify --zql in the command line, or specify --project, "
                                  + "--fixversion, --cyclename in the command line, or add project, "
                                  + "fixVersion, cycleName information in the project config file.")
                    sys.exit(1)
            args.file = MapConfigItemToArg(args.file, 'file', config, 'store', 'test_result.xml')
            args.ignore = MapConfigItemToArg(args.ignore, 'ignore', config, 'store_true')
            args.create = MapConfigItemToArg(args.create, 'create', config, 'store_true')
            args.add = MapConfigItemToArg(args.add, 'add', config, 'store_true')
            args.suite = MapConfigItemToArg(args.suite, 'suite', config)
            args.suiteFixVersion = MapConfigItemToArg(args.suiteFixVersion, 'suiteFixVersion', config)
        if args.command == 'maintenance':
            args.file = MapConfigItemToArg(args.file, 'file', config, 'store', 'testcase_input.xlsx')
            args.skipUpdate = MapConfigItemToArg(args.skipUpdate, 'skipTestUpdate', config, 'store_true')
            args.skipStepUpdate = MapConfigItemToArg(args.skipStepUpdate, 'skipStepUpdate', config, 'store_true')
            args.updateLink = MapConfigItemToArg(args.updateLink, 'updateLinks', config, 'store_true')
            args.ignore = MapConfigItemToArg(args.ignore, 'ignore', config, 'store_true')
            args.updateExecution = MapConfigItemToArg(args.updateExecution, 'updateExecution', config, 'store_true')
            args.updateStepExecution = MapConfigItemToArg(args.updateStepExecution, 'updateStepExecution', config, 'store_true')
            if args.updateExecution and not args.zql:
                if args.project and args.fixVersion and args.cycleName:
                    args.zql = 'project = \'' + args.project + '\' and ' + \
                        'fixVersion = \'' + args.fixVersion + '\' and ' + \
                        'cycleName in (\'' + args.cycleName + '\')'
                    logging.debug('ZQL: %s' % args.zql)
                else:
                    logging.error("Please specify --zql in the command line, or specify --project, --fixVersion, --cycleName in the command line, or add project, fixVersion, cycleName information in the project config file.")
                    sys.exit(1)
        if args.command == 'delete':
            if args.type == 'cycle' and not args.zql:
                if args.project and args.fixVersion and args.cycleName:
                    args.zql = 'project = \'' + args.project + '\' and ' + \
                        'fixVersion = \'' + args.fixVersion + '\' and ' + \
                        'cycleName in (\'' + args.cycleName + '\')'
                    logging.debug('ZQL: %s' % args.zql)
                else:
                    logging.error("Please specify --zql in the command line, or specify --project, "
                                  + "--fixversion, --cyclename in the command line, or add project, "
                                  + "fixVersion, cycleName information in the project config file.")
                    sys.exit(1)
        if args.command == 'export':
            args.testSteps = MapConfigItemToArg(args.testSteps, 'testSteps', config, 'store_true')
            if not args.jql and not args.zql:
                if args.project and args.fixVersion and args.cycleName:
                    args.zql = 'project = \'' + args.project + '\' and ' + \
                        'fixVersion = \'' + args.fixVersion + '\' and ' + \
                        'cycleName in (\'' + args.cycleName + '\')'
                    logging.debug('ZQL: %s' % args.zql)
                else:
                    logging.error("Please specify --jql or --zql in the command line, or specify --project, "
                                  + "--fixversion, --cyclename in the command line, or add project, "
                                  + "fixVersion, cycleName information in the project config file.")
                    sys.exit(1)
    logging.debug('args: %s' % args)
    #sys.exit(1)
    return args

def MapConfigItemToArg(arg, configItem, config, action = 'store', default = None):
    """
    Map a config item to the corresponding argument if an argument is not set in command.
    If it is not set in either command or config, then set it by default value
    :params arg: the argument to map to
    :params configItem: the config item in a config file
    :params config: the project config
    :params action: the type of the arguement
    :params default: the default value if no config item found in the project config
    """
    if not arg and config:
        if configItem in config:
            if action == 'store' and config[configItem].strip() <> '':
                return config[configItem].replace('\'','').strip()
            elif action == 'store_true' and config[configItem].strip() == 'Y':
                return True
            elif action == 'store_true' and config[configItem].strip() == 'N':
                return False
    elif arg:
        if action == 'store':
            return arg
            #return arg.strip().replace('\'','')
        elif action == 'store_true':
            return arg
    return default

def ParseJunit(file):
    """
    parse JUnit test result
    status hard coded in Intel JIRA: -1 - unexecuted; 1 - pass; 2 - failed; 3 - wip; 4 - blocked; 5 - not supported; 6 - not applicable;
    status from online doc but not in Intel JIRA: 20 - assigned; 22 - pending; 7 - verified; 23 - WIP; 15 - linked;
    :params file: the test result file
    :returns: a list of executions and duplicate test count in JUnit
    """
    import xunitparser
    if file:
        try:
            with open(file, 'r') as fileObj:
                ts, _ = xunitparser.parse(fileObj)
        except IOError:
            logging.error("The JUnit file %s cannot be found." % file)
            sys.exit(1)
    else:
        logging.error("Please specify your JUnit file by --file in command, or by file in config file.")
        sys.exit(1)

    tests = []
    status = '-1'
    duplicateTestCount = 0
    testcases = {}
    for tc in ts:
        if tc.skipped:
            status = '-1'
        elif tc.good:
            status = '1'
        elif tc.failed:
            status = '2'
        elif tc.errored:
            if tc.typename == "Blocked":
                status = '4'
            else:
                status = '5'
        else:
            status = '6'

        if tc.methodname in testcases:
            duplicateTestCount += 1
            logging.error("Duplicate test: %s" % tc.methodname)
            continue
        else:
            testcases[tc.methodname] = 1
            tests.append({"summary" : tc.methodname, "execution status" : status})

    if duplicateTestCount > 0:
        logging.error("Duplicate tests found in the test results: %d" % duplicateTestCount)
        logging.error("Please fix them before Zephyr upload.")
        sys.exit(1)
    return tests

def SetupCycle(args,zapi):
    '''
    Set up or retreieve project cycle information from JIRA/Zephyr
    :return: a list of project cycle relevant information
    '''
    (project, projectId, fixVersion, versionId, cycleName, cycleId) = GetCycleInfo(args.zql,zapi)

    if cycleId == -1:
        if args.newCycle:
            logging.info("Creating a new cycle...")
            cycleId = zapi.createNewCycle(projectId, cycleName, versionId, \
                args.startDate, args.endDate, args.build, args.environment, args.description)
            logging.info("New test cycle %s is created." % cycleName)
            logging.debug("New test cycleId is %s." % cycleId)
        else:
            logging.error("Cannot find cycle %s" % cycleName)
            sys.exit(1)
    else:
        if args.newCycle:
            #Below is to be discussed if we should remove this option "--newcycle" for production
            #if not args.debug:
            logging.error("The cycle %s already exists, please check the cycle name is correct." % cycleName)
            sys.exit(1)
        if args.startDate or args.endDate or args.build or args.environment or args.description:
            zapi.updateCycle(cycleId, versionId, args.startDate, args.endDate, args.build, \
                args.environment, args.description)
    return (project, projectId, fixVersion, versionId, cycleName, cycleId)

def GetCycleInfo(zql,zapi):
    '''
    get the exact ids of the project, the version and the cycle by the given zql statement
    '''
    data = parse_ZQL(zql)
    projectId = zapi.getProjectId(data['project'])
    logging.debug("projectId is %s." % projectId)
    versionId = zapi.getVersionId(data['project'], data['fixVersion'])
    logging.debug("versionId is %s, cycleName is %s." % (versionId, data['cycleName']))
    (cycleId, returnedVersionId) = zapi.listCycles(projectId, data['cycleName'], versionId)
    if cycleId == -1 or cycleId == None:
        cycleId = -1
    else:
        logging.info("Find cycle %s." % data['cycleName'])
        logging.debug("Find cycleId %s." % cycleId)
    return (data['project'], projectId, data['fixVersion'], versionId, data['cycleName'], cycleId)

def parse_ZQL(zql):
    '''
    parse the zql statement
    :return a dictionary of the relevant information
    '''
    project = ''
    cycleName = ''
    fixVersion = ''
    #all characters are accepted except whitespace characters, single and double quotation marks, but \' and \" is allowed in the following expression.
    match = re.search(r'project\s*=\s*[\'"]*\s*((\\\'|\\"|[^ \f\n\r\t\v\'"])+)\s*[\'"]*', zql)
    if match:
        project = match.groups()[0].replace("\\'","'").replace("\\\"","\"")
    else:
        logging.error("Cannot find project info from ZQL: %s" % zql)
        sys.exit(1)
    #all characters are accepted except single and double quotation marks, but \' and \" is allowed in the following expression.
    match = re.search(r'cycleName\s*in\s*\(\s*[\'"]*\s*((\\\'|\\"|[^\'"])*(\\\'|\\"|[^ \f\n\r\t\v\'"])+)\s*[\'"]*\s*\)', zql)
    if match:
        cycleName = match.groups()[0].replace("\\'","'").replace("\\\"","\"")
    else:
        logging.error("Cannot find cycleName info from ZQL: %s" % zql)
        sys.exit(1)
    #all characters are accepted except single and double quotation marks, but \' and \" is allowed in the following expression.
    match = re.search(r'fixVersion\s*=\s*[\'"]*\s*((\\\'|\\"|[^\'"])*(\\\'|\\"|[^ \f\n\r\t\v\'"])+)\s*[\'"]*', zql)
    if match:
        fixVersion = match.groups()[0].replace("\\'","'").replace("\\\"","\"")
    else:
        logging.error("Cannot find fixVersion info from ZQL: %s" % zql)
        sys.exit(1)
    logging.debug("project: %s, version: %s, cyclename: %s." % (project, fixVersion, cycleName))
    return dict(project=project, cycleName=cycleName, fixVersion=fixVersion)

def GetConfigPatternTests(profile, projectConfig):
    '''
    get the tests for verifying regular expression patterns
    :return a group of tests
    '''
    logFilePatternTests = ''
    testCasePatternTests = ''
    passPatternTests = ''
    failPatternTests = ''
    blockPatternTests = ''
    skipPatternTests = ''
    config = projectConfig[profile]
    if "logFilePatternTests" in config:
        logFilePatternTests = config["logFilePatternTests"]
    if "testCasePatternTests" in config:
        testCasePatternTests = config["testCasePatternTests"]
    if "passPatternTests" in config:
        passPatternTests = config["passPatternTests"]
    if "failPatternTests" in config:
        failPatternTests = config["failPatternTests"]
    if "blockPatternTests" in config:
        blockPatternTests = config["blockPatternTests"]
    if "skipPatternTests" in config:
        skipPatternTests = config["skipPatternTests"]

    return (logFilePatternTests, testCasePatternTests, passPatternTests, failPatternTests, blockPatternTests, skipPatternTests)

def GetComments(file):
    """
    update comment for non-passing JUnit test results
    :params file: the test result file
    :returns: a list of tests with comments
    """
    import xunitparser
    if file:
        try:
            with open(file, 'r') as fileObj:
                ts, _ = xunitparser.parse(fileObj)
        except IOError:
            logging.error("The JUnit file %s cannot be found." % file)
            sys.exit(1)
    else:
        logging.error("Please specify your JUnit file by --file in command, or by file in config file.")
        sys.exit(1)

    tests = []
    comment = ''
    duplicateTestCount = 0
    testcases = {}
    for tc in ts:
        if tc.skipped or tc.good:
            pass
        if tc.failed or tc.errored:
            if tc.methodname in tests:
                duplicateTestCount += 1
                continue
            else:
                testcases[tc.methodname] = 1
                tests.append(dict(summary=tc.methodname, comment=tc.stderr))
        else:
            pass

    if duplicateTestCount > 0:
        logging.warn("Duplicate tests found in the test results: %d" % duplicateTestCount)
    return tests

def addQuote(string):
    temp = ''
    if string <> None:
        if string[0] <> '\'':# and string[0] <> '"':
            temp = '\'' + string
        else:
            temp = string
        if string[-1] <> '\'': # and string[-1] <> '"':
            temp += '\''
    return temp
