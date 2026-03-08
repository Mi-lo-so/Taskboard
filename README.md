``` bash
poetry install    
```    

```bash
docker compose up -d
```

# edit .env with your DB credentials                                  
 alembic upgrade head                                                
     
```bash
 poetry run alembic upgrade head        
```
                                                                                                       
 Run migrations (requires a running Postgres, set DATABASE_URL in .env):                                                                                           
```bash                                                         
 cp .env.example .env           
```                        
                                                                                                                                                              
 Start the API locally:                                               
               
```bash                                             
 uvicorn main:app --reload 
```

 Deploy to AWS (requires AWS CLI credentials + CDK bootstrap):      
```bash
 npm install -g aws-cdk   # if not already installed   
```
```bash
 cdk bootstrap    
```
```bash
 cdk deploy   
```                 

 # After deploy, update DATABASE_URL in .env with the RDS endpoint from outputs                                                                                    
 alembic upgrade head
 
 Task model fields                                                                                                                                                                         
                                                                                                                                                                                                                 
     ┌──────────────────────────────────────────┬───────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────┐                                         
     │Field                                     │Type                                       │Notes                                                                │     
     ├──────────────────────────────────────────┼───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤  
     │id                                        │Integer PK                                 │auto-increment                                                       │                                              
     ├──────────────────────────────────────────┼───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤                                                                     
     ├──────────────────────────────────────────┼───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤                                              
     │description                               │Text                                       │nullable                                                             │  
     ├──────────────────────────────────────────┼───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤                                              
     │status                                    │Enum                                       │todo / in_progress / done, default todo                              │      
     ├──────────────────────────────────────────┼───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤                                              
     │progress                                  │Integer                                    │0–100 (DB check constraint), default 0                               │    
     ├──────────────────────────────────────────┼───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤                                              
     │created_at                                │DateTime(tz)                               │server default now()                                                 │  
     ├──────────────────────────────────────────┼───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤                                              
     │updated_at                                │DateTime(tz)                               │server default now(), auto-updated                                   │   
     └──────────────────────────────────────────┴───────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────┘                                              
                                                                                                                                                                                                                 
     API endpoints                                                                                                                                                                                               
                                                                                                                                                                                                                 
     ┌───────────────────────────────────────┬────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────────┐                                              
     │Method                                 │Path                                        │Description                                                            │                                              
     ├───────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤                                              
     │GET                                    │/tasks/                                     │List tasks (paginated with skip/limit)                                 │                                              
     ├───────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤                                              
     │POST                                   │/tasks/                                     │Create a task                                                          │                                              
     ├───────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤                                              
     │GET                                    │/tasks/{id}                                 │Get a single task                                                      │                                              
     ├───────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤                                              
     │PATCH                                  │/tasks/{id}                                 │Partially update a task                                                │                                              
     ├───────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────┤                                              
     │DELETE                                 │/tasks/{id}                                 │Delete a task                                                          │                                              
     └───────────────────────────────────────┴────────────────────────────────────────────┴───────────────────────────────────────────────────────────────────────┘                                              

## Curl

Create a task:
```bash
curl --header "Content-Type: application/json" --request POST --data '{"title":"SomeTask"}' http://localhost:8000/tasks
```
Get tasks:
```bash
curl http://localhost:8000/tasks
```

## CDK
### 1. Bootstrap (once per account/region)        
```bash
cdk bootstrap
```                                                                                                                                                                  
#### 2. Deploy infrastructure      
```bash
cdk deploy 
```                                                                                                                                            
                                                                                                                                                                                     
#### 3. Push your image to ECR (URI is in the stack outputs)    
```bash
ECR_URI=$(aws cloudformation describe-stacks --stack-name TaskBoardStack \                                                                                                              
--query "Stacks[0].Outputs[?OutputKey=='EcrRepositoryUri'].OutputValue" \                                                                                                             
--output text)       
```                                                                                                                                                                 
```bash                                                                                                                                    
aws ecr get-login-password --region eu-west-1 \                                                                                                                                         
| docker login --username AWS --password-stdin $ECR_URI      
```                                                                                                                         
  
```bash                                                                                                                                                                                   
docker build -t $ECR_URI:latest .   
```
```bash
docker push $ECR_URI:latest  
```                                                                                               
                                                                                                                                                                                     
# 4. Force ECS to pick up the new image         
```bash
aws ecs update-service --cluster TaskBoardCluster \                                                                                                                                     
--service TaskBoardService --force-new-deployment    
```