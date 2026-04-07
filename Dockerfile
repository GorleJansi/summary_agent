FROM public.ecr.aws/lambda/python:3.13

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy application code
COPY app.py ${LAMBDA_TASK_ROOT}/
COPY config.py ${LAMBDA_TASK_ROOT}/
COPY formatter.py ${LAMBDA_TASK_ROOT}/
COPY servicenow_client.py ${LAMBDA_TASK_ROOT}/
COPY summarizer.py ${LAMBDA_TASK_ROOT}/
COPY lambda_handler.py ${LAMBDA_TASK_ROOT}/

# Lambda handler: file.function
CMD ["lambda_handler.handler"]
