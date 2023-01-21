import docker
import boto3
import os

# Setup the boto3 client
cloudwatch = boto3.client('cloudwatch', region_name='us-east-1')
# set the AWS profile name; if you don't have one, remove this line or set it to "default."
boto3.setup_default_session(profile_name='devopsars')

# Setup the docker client
client = docker.from_env()

# Set of values units used in the cloudwatch
megabytes_values = {'mem_current', 'mem_total'}
percentage_values = {'cpu_percent', 'mem_percent'}
numbers_unit = {'status'}


def calculate_stats_summary(stats):
    name = stats['name'] # get the name of the container
    name = name.strip('/') # remove the / from the name
    mem_current = float(stats["memory_stats"]["usage"]/1024/1024/1024) # get the current memory usage
    mem_total = float(stats["memory_stats"]["limit"]/1024/1024/1024) # get the total memory usage
    mem_percent = round(float((mem_current / mem_total) * 100.0), 2) # calculate the percentage of memory usage
    cpu_count = stats['cpu_stats']['online_cpus'] # get the number of cpu cores
    cpu_percent = 0.0
    cpu_delta = float(stats["cpu_stats"]["cpu_usage"]["total_usage"]) - float(stats["precpu_stats"]["cpu_usage"]["total_usage"]) # get the cpu usage by the container
    system_delta = float(stats["cpu_stats"]["system_cpu_usage"]) - float(stats["precpu_stats"]["system_cpu_usage"]) # get the total cpu usage by the system

    # calculate the cpu usage percentage
    if system_delta > 0.0:
        cpu_percent = cpu_delta / system_delta * 100.0 * cpu_count
        cpu_percent = round(cpu_percent, 2)
    # create a dictionary with the stats summary to be sent to cloudwatch
    summary_stats = {'cpu_percent': cpu_percent,
                     'mem_current': mem_current, 'mem_percent': mem_percent, 'name': name}
    # print("cpu_percent: {} mem_current: {} mem_percent: {} name: {}".format(cpu_percent, mem_current, mem_percent, name))
    return summary_stats

def get_container_status():
    for container in client.containers.list():
        check_string = 'app' # To select only the containers that we want to monitor their status (up or down)
        if check_string in container.name:
            if container.status == 'running':
                status = 1
            elif container.status == 'exited':
                status = 0
            try:
                # send the status of the container to cloudwatch
                cloudwatch.put_metric_data(
                    MetricData=[
                        {
                            'MetricName': "Status",
                            'Dimensions': [
                                {
                                    'Name': 'Services Name',
                                    'Value': container.name
                                },
                                {
                                    'Name': 'Host Name',
                                    'Value': os.uname()[1]
                                },

                            ],
                            'Unit': 'None',
                            'Value': float(status)

                        },

                    ],
                    Namespace='Docker/Stats')

            except ValueError:
                    # print('not convertable key {}, value is: {}'.format(key, value))
                continue
        try:
            # get the stats of the container and send them to cloudwatch
            full_stats = container.stats(stream=False)
            summary_stats = calculate_stats_summary(full_stats)
            #detect the unit of the value and send it to cloudwatch
            for key in summary_stats:
                try:
                    if key in percentage_values:
                        unit = 'Percent'
                    elif key in megabytes_values:
                        unit = 'Megabytes'
                    else:
                        unit = 'None'
                    print("key: {}, value: {}".format(key,summary_stats[key])) #for deubgging
                    
                    ''' 
                    To send the stats to cloudwatch:
                    - MetricName is the name of the metric, this will appear in the cloudwatch console and we can filter by it
                    - Service Name is the name of the container that we are monitoring
                    - Host Name is the name of the host that the container is running on
                    - Unit is the unit of the value, this determines the unit of the value in the cloudwatch console
                    - Value is the value of the metric
                    - Namespace is the namespace of the metric in cloudwatch, this will appear in the cloudwatch console and all the keys will be under this namespace, we can change it to whatever we want
                    - Dimensions is the dimensions of the metric, we can add as much as we want, they are the columns in the cloudwatch console and we can filter by them, for example we can filter by the host name and see all the metrics of the host.
                    '''
                    cloudwatch.put_metric_data(
                        MetricData=[
                            {
                                'MetricName': key,
                                'Dimensions': [
                                    {
                                        'Name': 'Services Name',
                                        'Value': '{}'.format(summary_stats['name'])
                                    },
                                    {
                                        'Name': 'Host Name',
                                        'Value': os.uname()[1]
                                    },
                                ],
                                'Unit': unit,
                                'Value': float(summary_stats[key])

                            },
                        ],
                        Namespace='Docker/Stats')

                except ValueError:
                    # print('not convertable key {}, value is: {}'.format(key, value))
                    continue

        except KeyError:
            continue
    if __name__ == '__main__':
        get_container_status()

