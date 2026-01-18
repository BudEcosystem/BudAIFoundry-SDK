"""Example: Dapr Internal Service

Shows how to use BudClient for internal service-to-service calls with Dapr token.
This is typically used when your service runs inside the Bud platform.

The SDK automatically:
  - Defaults to http://localhost:3500 (Dapr sidecar)
  - Appends /v1.0/invoke/budpipeline/method to the URL
"""

from bud import Action, BudClient, Pipeline


def main():
    # For internal services running in the Bud platform,
    # use Dapr token authentication.
    #
    # The SDK automatically:
    # - Uses http://localhost:3500 as the default Dapr sidecar
    # - Constructs the full invoke URL: /v1.0/invoke/budpipeline/method/{endpoint}
    client = BudClient(
        dapr_token="your-dapr-token",
        user_id="user-id-to-act-as",  # Optional: user context
        # base_url defaults to http://localhost:3500 for Dapr auth
    )

    # Or use environment variables:
    # BUD_DAPR_TOKEN - Dapr API token
    # BUD_USER_ID - Optional user context
    # BUD_BASE_URL - Override sidecar URL if needed (defaults to localhost:3500)
    # client = BudClient()

    # Define and run pipeline
    with Pipeline("internal-pipeline") as p:
        step1 = Action("process", type="transform").with_config(
            input="${params.data}",
            operation="lowercase",
        )

        step2 = (
            Action("notify", type="log")
            .with_config(
                message="Processing complete",
                level="info",
            )
            .after(step1)
        )

    pipeline = client.pipelines.create(dag=p.to_dag(), name=p.name)
    print(f"Created pipeline: {pipeline.id}")

    execution = client.executions.create(pipeline.id, params={"data": "HELLO"})
    print(f"Execution: {execution.effective_id}")
    print(f"Status: {execution.status}")


if __name__ == "__main__":
    main()
