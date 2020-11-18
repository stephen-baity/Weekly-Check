import boto3
import botocore
import datetime
import time

# Procedure used to find any day of the week from today
def next_weekday(d, weekday):
    days_ahead = weekday - d.weekday()
    if days_ahead <= 0: # Target day already happened this week
        days_ahead += 7
    return d + datetime.timedelta(days_ahead)

todaydate = datetime.datetime.now()
pastSunday = next_weekday(todaydate, 6) - datetime.timedelta(days=7)
pastSundayFormatted = pastSunday.strftime("%Y%m%d")


print("Checking disk space and virus scans from {0}".format(pastSundayFormatted))

#Creating the lists that will hold the instances are ignored, have errors, or not checked
ignoredInstances = [ 'i-013644c02a33bec66']
errors = []
uncheckedInstances = []

accounts = ['dtwh-west','default', 'fwv', 'fwv-tnc', 'versobio']

# In each account, iterate through and send the a disk space/clamscan command to all running instances.
for account in accounts:
    print('Logging into {0}'.format(account))
    session = boto3.session.Session(profile_name=account)
    ec2 = session.resource('ec2')
    ssm = session.client('ssm')

    running_instances = []

    print('Finding running instances')
    for instance in ec2.instances.all():
        if (instance.state['Code'] == 16):
            if (instance.instance_id in ignoredInstances):
                continue
            running_instances.append(instance.instance_id)
            for tag in instance.tags:
                if tag['Key'] == 'Name':
                    name = tag['Value']
                    print('Checking {0}...'.format(name))

            #Send command to the instance, and catch any errors.
            try:
                response = ssm.send_command(
                    InstanceIds=[
                        instance.id,
                    ],
                    DocumentName="AWS-RunShellScript",
                    Parameters={
                        'commands': [
                            'uname -a', 'df -h', 'cat /var/log/clamav/clamscan.log-{0}'.format(pastSundayFormatted),
                            'cat /var/log/clamav/clamd.log-{0}'.format(pastSundayFormatted), 'cat /var/log/clamscan.log',
                            'cat /var/log/clamav/clamscan.log'
                        ]
                    },
                )
                #Get the console output from the command that was just executed
                time.sleep(3)
                command_id = response['Command']['CommandId']
                output = ssm.get_command_invocation(
                    CommandId=command_id,
                    InstanceId=instance.instance_id
                )

                #Check disk space percenteage and scan output for infected files or malformed database
                output = output['StandardOutputContent']
                splitoutput = output.splitlines()
                for line in splitoutput:
                    if line.startswith('/dev/xvda1'):
                        percent = int(line.split()[4].strip('%'))
                        if (percent >= 80):
                            errors.append('{0}: disk use is at {1}%'.format(name, percent))
                    if line.startswith('Infected files:'):
                        infectedFiles = int(line.split()[2])
                        if infectedFiles > 0:
                            errors.append('{0}: {1} infected file(s)'.format(name, infectedFiles))

                if ("ERROR: Malformed database") in output:
                    errors.append('{0}: malformed database'.format(name))
            #If the instance cannot be scanned, add the instance to the list of unchecked instances along with the error
            except botocore.exceptions.ClientError as error:
                uncheckedInstances.append(
                    {
                        "Name": name,
                        "error": error
                    }
                )
    print("-----------------------------------------------------------------------------")
    print("")

#If no errors, print 'no errors'
if not errors:
    print('No errors')
else:
    print('Errors found:')
    for error in errors:
        print(error)

print("")
#Print the instances that weren't checked
if len(uncheckedInstances) > 0:
    print('Unchecked Instances:')
    for instance in uncheckedInstances:
        print('{0} ({1})'.format(instance["Name"], instance['error']))



