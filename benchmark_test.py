import kaggle_benchmarks as kbench


@kbench.task(name="simple-test", description="Simple RAG system sanity check")
def simple_test(llm) -> None:
    response = llm.prompt("Hello! Are you ready?")
    kbench.assertions.assert_true(
        len(response) > 0, expectation="Response is not empty"
    )


if __name__ == "__main__":
    simple_test.run(kbench.llm)
