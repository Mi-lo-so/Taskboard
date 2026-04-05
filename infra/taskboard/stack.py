from typing import Any

import aws_cdk as cdk
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecr as ecr
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_elasticloadbalancingv2 as elbv2
import aws_cdk.aws_iam as iam
import aws_cdk.aws_logs as logs
import aws_cdk.aws_rds as rds
import aws_cdk.aws_secretsmanager as secretsmanager
from constructs import Construct
from pydantic import BaseModel


class SecurityGroups(BaseModel):
    app_load_balancer_security_group: Any
    app_security_group: Any
    db_security_group: Any


class TaskBoardStack(cdk.Stack):
    """CDK stack that provisions the full Task Board infrastructure.

    Uses Fargate to run the app.
    ECR is used to store images for the task definitions.
    A RDS db (postgres) for storing the tasks individual of Fargate
    A load balancer


    Resources created:
      - VPC with public, private (egress), and isolated subnet tiers across 2 AZs
      - ECR repository for the FastAPI container image
      - ECS Fargate cluster + task definition + service (2 tasks by default)
      - ALB (Application Load Balancer) (internet-facing) on port 80
      - RDS PostgreSQL 16 instance (db.t3.micro) in isolated subnets
      - Secrets Manager secret holding DB credentials
      - Security groups with least-privilege rules:
          ALB  → Fargate  (port 8000)
          Fargate → RDS   (port 5432)
      - IAM task role granting Fargate read access to the DB secret
      - DATABASE_URL injected into the Fargate container from Secrets Manager

    Deployment workflow (once):
      1. infra bootstrap
      2. infra deploy
      3. docker build -t <ecr_uri>:latest .
         aws ecr get-login-password | docker login --username AWS --password-stdin <ecr_uri>
         docker push <ecr_uri>:latest
      4. Force a new ECS deployment:
         aws ecs update-service --cluster TaskBoardCluster --service TaskBoardService --force-new-deployment
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc(
            self,
            "TaskBoardVpc",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=28,
                ),
            ],
        )

        container_image_repository = ecr.Repository(
            self,
            "TaskBoardRepository",
            repository_name="taskboard_image_repository",
            removal_policy=cdk.RemovalPolicy.DESTROY,
            empty_on_delete=True,
            lifecycle_rules=[
                # Keep only the most recent image to control storage costs
                ecr.LifecycleRule(max_image_count=1)
            ],
        )
        """ECR repository for the container image, used in the task(s) for the fargate service."""

        rds_secret = secretsmanager.Secret(
            self,
            "TaskBoardDbSecret",
            secret_name="TaskBoardDbSecret",
            description="RDS credentials for the Task Board database",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "taskboard"}',
                generate_string_key="password",
                exclude_punctuation=True,
                password_length=32,
            ),
        )

        security_groups = self.create_security_groups(vpc)
        db_security_group = security_groups.db_security_group
        app_load_balancer_security_group = (
            security_groups.app_load_balancer_security_group
        )
        app_security_group = security_groups.db_security_group

        rds_db_instance = rds.DatabaseInstance(
            self,
            "TaskBoardDb",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            security_groups=[db_security_group],
            credentials=rds.Credentials.from_secret(rds_secret),
            database_name="taskboard",
            allocated_storage=20,
            max_allocated_storage=100,
            storage_type=rds.StorageType.GP2,
            multi_az=False,  # set True for production HA
            deletion_protection=False,  # set True for production
            removal_policy=cdk.RemovalPolicy.DESTROY,
            backup_retention=cdk.Duration.days(7),
            publicly_accessible=False,
        )

        # Task execution role — used by ECS to pull the image and fetch secrets
        execution_role = iam.Role(
            self,
            "TaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
        )
        # Grant the execution role permission to read the DB secret so ECS can
        # inject it as an environment variable at task startup
        rds_secret.grant_read(execution_role)

        # Task role — the IAM identity the running application code assumes
        task_role = iam.Role(
            self,
            "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        task_definition = ecs.FargateTaskDefinition(
            self,
            "TaskBoardTaskDef",
            cpu=256,
            memory_limit_mib=512,
            execution_role=execution_role,
            task_role=task_role,
        )

        log_group = logs.LogGroup(
            self,
            "TaskBoardLogGroup",
            log_group_name="/ecs/taskboard",
            retention=logs.RetentionDays.ONE_DAY,  # no need to keep for long
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # Build the DATABASE_URL from secret fields + the RDS endpoint.
        # ECS resolves Secrets Manager ARN references at task launch time.
        database_url = (
                "postgresql://"
                + rds_secret.secret_value_from_json("username").unsafe_unwrap()
                + ":"
                + rds_secret.secret_value_from_json("password").unsafe_unwrap()
                + "@"
                + rds_db_instance.db_instance_endpoint_address
                + ":5432/taskboard"
        )

        task_definition.add_container(
            "TaskBoardContainer",
            image=ecs.ContainerImage.from_ecr_repository(
                container_image_repository, tag="latest"
            ),
            environment={
                "DATABASE_URL": database_url,
            },
            port_mappings=[ecs.PortMapping(container_port=8000)],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="taskboard",
                log_group=log_group,
            ),
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:8000/ || exit 1"],
                interval=cdk.Duration.seconds(30),
                timeout=cdk.Duration.seconds(5),
                retries=3,
                start_period=cdk.Duration.seconds(60),
            ),
        )

        ecs_fargate_cluster = ecs.Cluster(
            self,
            "TaskBoardCluster",
            cluster_name="TaskBoardCluster",
            vpc=vpc,
        )

        service = ecs.FargateService(
            self,
            "TaskBoardService",
            service_name="TaskBoardService",
            cluster=ecs_fargate_cluster,
            task_definition=task_definition,
            desired_count=2,
            min_healthy_percent=100,
            max_healthy_percent=200,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[app_security_group],
            assign_public_ip=False,
        )

        app_load_balancer = elbv2.ApplicationLoadBalancer(
            self,
            "TaskBoardAlb",
            vpc=vpc,
            internet_facing=True,
            security_group=app_load_balancer_security_group,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        listener = app_load_balancer.add_listener(
            "HttpListener",
            port=80,
            open=False,  # security group controls access, not CDK's auto-open
        )

        listener.add_targets(
            "TaskBoardTargets",
            port=8000,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[service],
            health_check=elbv2.HealthCheck(
                path="/",
                healthy_http_codes="200",
                interval=cdk.Duration.seconds(30),
                timeout=cdk.Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
            ),
            deregistration_delay=cdk.Duration.seconds(30),
        )

        cdk.CfnOutput(
            self,
            "AlbDnsName",
            value=app_load_balancer.load_balancer_dns_name,
            description="Application Load Balancer DNS name — use as the API base URL",
            export_name="TaskBoardAlbDnsName",
        )
        cdk.CfnOutput(
            self,
            "EcrRepositoryUri",
            value=container_image_repository.repository_uri,
            description="ECR repository URI — push your Docker image here",
            export_name="TaskBoardEcrRepositoryUri",
        )
        cdk.CfnOutput(
            self,
            "DbEndpoint",
            value=rds_db_instance.db_instance_endpoint_address,
            description="RDS instance endpoint hostname",
            export_name="TaskBoardDbEndpoint",
        )
        cdk.CfnOutput(
            self,
            "DbSecretArn",
            value=rds_secret.secret_arn,
            description="ARN of the Secrets Manager secret holding DB credentials",
            export_name="TaskBoardDbSecretArn",
        )
        cdk.CfnOutput(
            self,
            "VpcId",
            value=vpc.vpc_id,
            description="VPC ID",
            export_name="TaskBoardVpcId",
        )

        # Expose for cross-stack references if needed
        self.vpc = vpc
        self.repository = container_image_repository
        self.db_instance = rds_db_instance
        self.db_secret = rds_secret  # TODO reconsider if this is safe / CfnOutput may be enough, if a SM isnt
        self.alb = app_load_balancer

    def create_security_groups(self, vpc) -> SecurityGroups:
        # ALB — accepts inbound HTTP from the internet
        app_load_balancer_security_group = ec2.SecurityGroup(
            self,
            "AlbSecurityGroup",
            vpc=vpc,
            description="Allow HTTP from the internet to the ALB",
            allow_all_outbound=False,
        )
        app_load_balancer_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="HTTP from internet",
        )

        # Fargate app
        app_security_group = ec2.SecurityGroup(
            self,
            "AppSecurityGroup",
            vpc=vpc,
            description="Allow port 8000 from ALB to Fargate tasks",
            allow_all_outbound=True,  # needs outbound to reach RDS and Secrets Manager
        )

        # Allow ALB to reach (ingress) Fargate app, and app to reach (egress) ALB
        app_security_group.add_ingress_rule(
            peer=app_load_balancer_security_group,
            connection=ec2.Port.tcp(8000),
            description="Port 8000 from ALB",
        )
        app_load_balancer_security_group.add_egress_rule(
            peer=app_security_group,
            connection=ec2.Port.tcp(8000),
            description="Forward to Fargate on port 8000",
        )

        # RDS — accepts inbound on 5432 from Fargate only
        db_security_group = ec2.SecurityGroup(
            self,
            "DbSecurityGroup",
            vpc=vpc,
            description="Allow PostgreSQL access from Fargate tasks only",
            allow_all_outbound=False,
        )
        db_security_group.add_ingress_rule(
            peer=app_security_group,
            connection=ec2.Port.tcp(5432),
            description="PostgreSQL from Fargate",
        )

        return SecurityGroups(
            app_load_balancer_security_group=app_load_balancer_security_group,
            app_security_group=app_security_group,
            db_security_group=db_security_group,
        )
