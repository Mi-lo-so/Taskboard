#!/usr/bin/env python3
"""AWS CDK application entry point for the Task Board infrastructure."""

import os
import sys

import aws_cdk as cdk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.taskboard.stack import TaskBoardStack

app = cdk.App()

TaskBoardStack(
    app,
    "TaskBoardStack",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "eu-west-1",
    ),
    description="Task Board Stack - RDS and Fargate with ALB",
)

app.synth()
