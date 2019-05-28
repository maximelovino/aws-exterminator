# AWS Exterminator

AWS Exterminator is a command-line tool to help you discover and delete unused instances, EBS volumes and AMI images across all regions in your AWS account. The program will suggest resources to delete based on metrics returned by CloudWatch. You can also view any available metrics for all instances.

## Demonstration

![](demo.gif)

## Suggestion for deleting instances

When the user wants to delete instance, we will iterate over each instance to determine if we should suggest deleting the instance. First of all, if the instance is `stopped`, it often means that the instance has been forgotten so we will suggest deleting the instance. Then, we will use 3 metrics: CPU Usage, Network bytes in and Network bytes out. The user will choose the thresholds for CPU and Network and then we will check if the values are below the thresholds first for the last week, then for the last day and finally for the last hour. As soon as we have a value below a threshold, we will mark the instance as deletable and display the reason to the user.

The instances marked for deletion will be separated by a separator in the menu from the other instances.

## Third-parties libraries

- [Numpy](https://github.com/numpy/numpy) for manipulating arrays more easily
- [Boto3](https://github.com/boto/boto3) to interact with AWS
- [PyInquirer](https://github.com/CITGuru/PyInquirer) to have an interactive and fancy CLI
- [Tableprint](https://github.com/nirum/tableprint) to display tables nicely

## How to run

You need to create a file named `.env` in the root folder of the project, containing:

```
AWS_ACCESS_KEY_ID=<accesskey>
AWS_SECRET_ACCESS_KEY=<secretkey>
AWS_DEFAULT_REGION=<defaultregion>
```

The default region is required by the AWS sdk but the program will check every AWS region anyway.

The program is written in Python 3.

Then, you can install the requirements present in `requirements.txt` by using `pip`:

```
pip install -r requirements.txt
```

And finally launch the program:

```
python exterminator.py
```

Then you can follow the on-screen instructions to use the program.