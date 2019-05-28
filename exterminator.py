import boto3
from dotenv import load_dotenv
from datetime import datetime, timedelta
import tableprint as tp
import numpy as np
from PyInquirer import prompt, Separator

load_dotenv()

ec2_client = boto3.client('ec2')

response = ec2_client.describe_regions()
regions = list(map(lambda x: x['RegionName'], response['Regions']))

regions_clients = {region: boto3.resource('ec2', region_name=region) for region in regions}
regions_cloudwatches = {region: boto3.client('cloudwatch', region_name=region) for region in regions}

np_len = np.vectorize(len)


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def find_all_instances():
    instances_dict = {}
    all_metrics = []
    for reg in regions:
        print(f"\r\033[KAnalysing region '{reg}'...", end='')

        ec2 = regions_clients[reg]
        instances = list(ec2.instances.all())

        if len(instances) > 0:
            instances_dict[reg] = {}
        else:
            continue
        for instance in instances:
            instances_dict[reg][instance.id] = instance
            watch = regions_cloudwatches[reg]
            metrics = watch.list_metrics(Namespace='AWS/EC2', Dimensions=[{"Name": "InstanceId",
                                                                           "Value": instance.id}])
            metrics = metrics['Metrics']
            for met in metrics:
                if not next((x for x in all_metrics if x['name'] == met['MetricName']), None):
                    all_metrics.append({'name': met['MetricName'], 'value': met})
    print("\r\033[K...Got all instances")

    all_metrics.sort(key=lambda x: x['name'])

    return instances_dict, all_metrics


def get_instance_link(region, instance_id):
    return f"https://console.aws.amazon.com/ec2/v2/home?region={region}#Instances:instanceId={instance_id};sort=instanceId"


def instances_pretty_print(instances):
    def get_instance_array(instance):
        if instance.tags:
            name = next((item['Value'] for item in instance.tags if item["Key"] == "Name"), "-----")
        else:
            name = "-----"
        return np.array(
            [instance.launch_time.strftime("%m/%d/%Y, %H:%M:%S"), instance.id, name, instance.instance_type, instance.image_id, instance.state['Name'],
             instance.public_dns_name])

    for region in instances.keys():
        print(f"{region}:")
        headers = np.array(["Creation Date", "ID", "Name", "Type", "AMI", "State", "Public DNS"])
        data = np.array(list(map(get_instance_array, instances[region].values())))
        width = np_len(np.append(headers.reshape(1, -1), data, axis=0)).max(axis=0)
        tp.table(data, headers, width=width)


def metric_for_instance(period, met, instance_id, watch_client):
    dimensions = [{'Name': 'InstanceId', 'Value': instance_id}]
    response = watch_client.get_metric_statistics(Namespace=met['Namespace'], MetricName=met['MetricName'], Dimensions=dimensions, Statistics=[
        'SampleCount', 'Average', 'Sum', 'Minimum', 'Maximum',
    ], Period=period, EndTime=datetime.utcnow(), StartTime=datetime.utcnow() - timedelta(seconds=period))
    if not response or not response['Datapoints']:
        raise Exception
    data = response['Datapoints'][0]
    return data


def print_metrics(period, met, instances):
    print(met['MetricName'])
    for region in instances.keys():

        headers = np.array(["ID", "Min", "Max", "Average", "Sum", "Sample count"])
        watch = regions_cloudwatches[region]
        metrics = []
        for instance_id in instances[region].keys():
            if not instances[region][instance_id].state['Name'] == 'running':
                continue
            try:
                data = metric_for_instance(period, met, instance_id, watch)
                for data_key in ['Minimum', 'Maximum', 'Average', 'Sum']:
                    if data['Unit'] == 'Bytes':
                        data[data_key] = sizeof_fmt(data[data_key])
                    elif data['Unit'] == 'Percent':
                        data[data_key] = f"{data[data_key]} %"
                    elif not data['Unit'] == 'Count':
                        data[data_key] = f"{data[data_key]} {data['Unit']}"
                metrics.append([instance_id, data['Minimum'], data['Maximum'], data['Average'], data['Sum'], data['SampleCount']])
            except:
                print(f"Couldn't get metrics for {instance_id}")
        if len(metrics) > 0:
            print(f"{region}:")
            metrics = np.array(metrics)
            width = np_len(np.append(headers.reshape(1, -1), metrics, axis=0)).max(axis=0)
            tp.table(metrics, headers, width=width)


def delete_instance(instance_id, region):
    client = boto3.client('ec2', region_name=region)
    client.terminate_instances(InstanceIds=[instance_id], DryRun=False)


def get_all_images():
    images_dict = {}
    for reg in regions:
        print(f"\r\033[KAnalysing region '{reg}'...", end='')

        ec2 = regions_clients[reg]
        images = list(ec2.images.filter(Owners=['self']))

        if len(images) > 0:
            images_dict[reg] = {}
        else:
            continue
        for image in images:
            images_dict[reg][image.id] = image
    print("\r\033[K...Got all images")
    return images_dict


def images_pretty_print(images):
    def get_image_array(image):
        # For creation date, we should parse as datetime and then strftime("%m/%d/%Y, %H:%M:%S")
        return np.array(
            [image.creation_date, image.id, image.name, image.image_type])

    for region in images.keys():
        print(f"{region}:")
        headers = np.array(["Creation Date", "ID", "Name", "Type"])
        data = np.array(list(map(get_image_array, images[region].values())))
        width = np_len(np.append(headers.reshape(1, -1), data, axis=0)).max(axis=0)
        tp.table(data, headers, width=width)


def get_all_volumes():
    volumes_dict = {}
    for reg in regions:
        print(f"\r\033[KAnalysing region '{reg}'...", end='')

        ec2 = regions_clients[reg]
        volumes = list(ec2.volumes.all())

        if len(volumes) > 0:
            volumes_dict[reg] = {}
        else:
            continue
        for volume in volumes:
            volumes_dict[reg][volume.id] = volume
    print("\r\033[K...Got all volumes")
    return volumes_dict


def volumes_pretty_print(volumes):
    def get_volume_array(volume):
        # For creation date, we should parse as datetime and then strftime("%m/%d/%Y, %H:%M:%S")
        return np.array(
            [volume.create_time.strftime("%m/%d/%Y, %H:%M:%S"), volume.id, volume.iops, volume.volume_type, volume.size])

    for region in volumes.keys():
        print(f"{region}:")
        headers = np.array(["Creation Date", "ID", "IOPS", "Type", "Size"])
        data = np.array(list(map(get_volume_array, volumes[region].values())))
        width = np_len(np.append(headers.reshape(1, -1), data, axis=0)).max(axis=0)
        tp.table(data, headers, width=width)


def delete_decision(instance, region, all_metrics, cpu_max_threshold, network_threshold):
    hour_period = 60 * 60
    day_period = 24 * hour_period
    week_period = 7 * day_period

    periods = [(week_period, "last week"), (day_period, "last day"), (hour_period, "last hour")]

    cpu_metric = next((x['value'] for x in all_metrics if x['name'] == 'CPUUtilization'), None)
    network_in_metric = next((x['value'] for x in all_metrics if x['name'] == 'NetworkIn'), None)
    network_out_metric = next((x['value'] for x in all_metrics if x['name'] == 'NetworkOut'), None)
    watch_client = regions_cloudwatches[region]

    if instance.state['Name'] == 'stopped':
        return True, "Instance is stopped", None, None

    for (period, period_name) in periods:
        try:
            if cpu_metric:
                cpu = metric_for_instance(period, cpu_metric, instance.id, watch_client)
                if cpu['Maximum'] <= cpu_max_threshold:
                    return True, f"CPU Usage smaller or equal to {cpu_max_threshold} % over {period_name}", cpu_metric, period

            if network_in_metric:
                network_in = metric_for_instance(period, network_in_metric, instance.id, watch_client)
                if network_in['Sum'] <= network_threshold:
                    return True, f"Network in smaller or equal to {sizeof_fmt(network_threshold)} over {period_name}", network_in_metric, period

            if network_out_metric:
                network_out = metric_for_instance(period, network_out_metric, instance.id, watch_client)
                if network_out['Sum'] <= network_threshold:
                    return True, f"Network out smaller or equal to {sizeof_fmt(network_threshold)} over {period_name}", network_out_metric, period
        except:
            print(f"Couldn't get metrics for {instance_id}")
    return False, "", None, None


all_instances, all_metrics = find_all_instances()

if len(all_instances) == 0:
    print("You don't have any instances running...bye...")
    exit(0)

running = True

menu_question = [{
    'type': 'list',
    'name': 'menu',
    'message': 'What do you want to do next?',
    'choices': [
        {'name': "Refresh instance list", 'value': 'r'},
        {'name': "Choose an instance to delete", 'value': 'd'},
        {'name': "View metrics", 'value': 'm'},
        {'name': "View images", 'value': 'i'},
        {'name': "View volumes", 'value': 'v'},
        {'name': "Quit", 'value': 'q'},
    ]
}]
instances_pretty_print(all_instances)
# List all instances
while running:
    menu_answer = prompt(menu_question)
    key = menu_answer['menu']

    if key == 'q':
        running = False
    elif key == 'd':
        if len(all_metrics) == 0:
            print("No metrics available at the moment")
            continue

        print("We will check the specified criterias for periods of 1 day and 1 hour with decreasing priority")
        criterias = [{
            'type': 'list',
            'name': 'cpu',
            'message': 'What max CPU threshold do you want to use?',
            'choices': [{'name': f'< {x} %', 'value': x} for x in [0, 1, 5, 10, 20]]
        }, {
            'type': 'list',
            'name': 'network',
            'message': 'What network threshold do you want to use?',
            'choices':
                [{'name': f'< {sizeof_fmt(x)}', 'value': x} for x in [512, 100 * 1024, 1024 ** 2, 10 * 1024 ** 2]]
        }]

        answers = prompt(criterias)

        instances_to_delete = []
        normal_instances = []
        for region in all_instances.keys():
            for instance_id in all_instances[region].keys():
                instance = all_instances[region][instance_id]
                if instance.state['Name'] in ['shutting-down', 'terminated']:
                    continue
                delete = delete_decision(instance, region, all_metrics, answers['cpu'], answers['network'])
                if delete[0]:
                    instances_to_delete.append({'name': f"{region}: {instance_id} => {delete[1]}",
                                                'value': {'region': region, 'id': instance_id, 'metric': delete[2], 'period': delete[3]}})
                else:
                    normal_instances.append({'name': f"{region}: {instance_id}",
                                             'value': {'region': region, 'id': instance_id}})

        to_delete_questions = [{
            'type': 'list',
            'name': 'instance',
            'message': 'What instance do you want to delete?',
            'choices': instances_to_delete + [Separator()] + normal_instances + [Separator(), {'name': "Don't delete anything", 'value': None}]
        }]
        answers = prompt(to_delete_questions)

        if 'instance' in answers:
            instance = answers['instance']
            confirmation_question = [{
                'type': 'confirm',
                'message': f"Are you sure you want to delete instance {instance['id']}?",
                'name': 'delete',
                'default': True,
            }]
            confirmation = prompt(confirmation_question)

            if confirmation['delete']:
                print("Deleting instance...")
                delete_instance(instance['id'], instance['region'])
                print("...Done")
        pass
    elif key == 'm':
        if len(all_metrics) == 0:
            print("No metrics available at the moment")
            continue

        metrics_questions = [{
            'type': 'list',
            'name': 'metric',
            'message': 'What metric do you want to see?',
            'choices': all_metrics
        }, {
            'type': 'list',
            'name': 'duration',
            'message': 'For how long?',
            'choices': [
                {'name': '10 minutes', 'value': 600},
                {'name': '1 hour', 'value': 3600},
                {'name': '24 hours', 'value': 86400}
            ]
        }]
        answers = prompt(metrics_questions)
        print_metrics(answers['duration'], answers['metric'], all_instances)
    elif key == 'r':
        all_instances, all_metrics = find_all_instances()
        instances_pretty_print(all_instances)
    elif key == 'i':
        # get other resources types
        images = get_all_images()
        images_pretty_print(images)
        pass
    elif key == 'v':
        volumes = get_all_volumes()
        volumes_pretty_print(volumes)
    else:
        print("Unsupported operation")

print("Bye")
