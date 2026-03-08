#!/usr/bin/env python3
"""AWS CDK application entry point for the Task Board infrastructure."""

import aws_cdk as cdk

from cdk.taskboard_stack import TaskBoardStack

app = cdk.App()

TaskBoardStack(
    app,
    "TaskBoardStack",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "eu-west-1",
    ),
    description="Task Board – VPC + RDS PostgreSQL",
)

app.synth()
