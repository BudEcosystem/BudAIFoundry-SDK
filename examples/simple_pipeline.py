"""Example: Simple Pipeline

Shows how to create and run a pipeline programmatically using BudClient.
"""

from bud import BudClient, Pipeline, Action


def main():
    # Option 1: Use stored tokens from `bud auth login`
    client = BudClient()

    # Option 2: Explicit credentials
    # client = BudClient(
    #     email="your-email@example.com",
    #     password="your-password",
    # )

    # Option 3: API key
    # client = BudClient(api_key="your-api-key")

    # Option 4: Environment variables (BUD_EMAIL, BUD_PASSWORD, BUD_API_URL)
    # client = BudClient()

    # Define pipeline using DSL
    with Pipeline("simple-pipeline") as p:
        start = Action("start", type="log").with_config(
            message="Pipeline started",
            level="info",
        )

        transform = Action("transform", type="transform").with_config(
            input="hello world",
            operation="uppercase",
        ).after(start)

        output = Action("output", type="set_output").with_config(
            key="result",
            value="${steps.transform.output}",
        ).after(transform)

    # Create pipeline via API
    pipeline = client.pipelines.create(
        dag=p.to_dag(),
        name=p.name,
        description="Simple example pipeline",
    )
    print(f"Created pipeline: {pipeline.id}")

    # Execute the pipeline
    execution = client.executions.create(pipeline.id)
    print(f"Execution: {execution.effective_id}")
    print(f"Status: {execution.status}")


if __name__ == "__main__":
    main()
