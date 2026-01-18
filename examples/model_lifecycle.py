"""Example: Model Lifecycle Pipeline

Shows how to create a model lifecycle pipeline with BudClient.
"""

from bud import BudClient, Pipeline, Action


def main():
    # Initialize client - uses stored tokens from `bud auth login`
    client = BudClient()

    # Or with explicit credentials:
    # client = BudClient(
    #     email="your-email@example.com",
    #     password="your-password",
    # )

    # Define model lifecycle pipeline
    with Pipeline("model-lifecycle") as p:
        start = Action("start", type="log").with_config(
            message="Starting model lifecycle pipeline",
            level="info",
        )

        # Add model from HuggingFace
        add_model = Action("add-model", type="model_add").with_config(
            model_source="hugging_face",
            model_uri="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            description="Model added via pipeline",
        ).with_timeout(3600).after(start)

        # Run benchmark
        benchmark = Action("benchmark", type="model_benchmark").with_config(
            model_id="${steps.add-model.output.model_id}",
            benchmark_type="performance",
        ).with_timeout(7200).after(add_model)

        # Deploy the model
        deploy = Action("deploy", type="deployment_create").with_config(
            model_id="${steps.add-model.output.model_id}",
            name="model-deployment",
            replicas=1,
        ).after(benchmark)

    # Create and execute
    pipeline = client.pipelines.create(
        dag=p.to_dag(),
        name=p.name,
    )
    print(f"Created pipeline: {pipeline.id}")

    execution = client.executions.create(pipeline.id)
    print(f"Execution: {execution.effective_id}")
    print(f"Status: {execution.status}")


if __name__ == "__main__":
    main()
