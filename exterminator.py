from dotenv import load_dotenv

load_dotenv()

import boto3

ec2_client = boto3.client('ec2')

response = ec2_client.describe_regions()
regions = list(map(lambda x: x['RegionName'], response['Regions']))

regions_clients = list(map(lambda region: boto3.resource('ec2', region_name=region), regions))


for i,client in enumerate(regions_clients):
    print("Region: ", regions[i])
    instances = client.instances.all()
    for i in instances:
        print(i)