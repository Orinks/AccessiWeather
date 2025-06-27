
# AI Development Rules for AccessiWeather Migration

This document outlines the rules and procedures for the AI to follow during the migration of the AccessiWeather application from `wxPython` to `Toga`. The primary goal is to ensure a smooth, test-driven migration that results in a clean, maintainable, and well-documented codebase.

## 1. Taskmaster Workflow

All development work will be managed through Taskmaster. The following workflow must be followed:

1.  **Initialize Project**: The project is already initialized.
2.  **Analyze Project**: Before starting any work, analyze the project structure to understand the current state of the codebase.
3.  **Create Tasks**: Create a `prd.md` file that outlines the project goals, and then use `task-master parse-prd` to generate the initial set of tasks. The tasks should be broken down into small, manageable chunks.
4.  **Follow Task-Driven Development**: Use `task-master next` to get the next task, `task-master expand` to break down complex tasks, and `task-master set-status` to update the status of tasks.
5.  **Implement and Test**: For each task, write the necessary implementation and tests. Follow the test-driven development (TDD) approach described below.
6.  **Update Tasks**: If the implementation differs from the original plan, use `task-master update-task` to update the task details.

## 2. Test-Driven Development (TDD)

TDD is mandatory for this project. The following TDD cycle must be followed for every new feature or piece of functionality:

1.  **Write a Failing Test**: Before writing any implementation code, write a test that will fail because the feature doesn't exist yet.
2.  **Run the Test**: Run the test to ensure that it fails as expected.
3.  **Write the Implementation**: Write the minimum amount of code required to make the test pass.
4.  **Run the Test Again**: Run the test again to ensure that it now passes.
5.  **Refactor**: Refactor the code to improve its design, readability, and performance, without changing its behavior.

All tests should be written using the `pytest` framework.

## 3. BeeWare/Toga and Briefcase Best Practices

The migrated application must follow BeeWare/Toga and Briefcase best practices to ensure that it is cross-platform compatible and easily deployable. The following rules must be adhered to:

1.  **Project Structure**: The project must follow the standard BeeWare project structure. The main application logic should be in `src/accessiweather/simple`.
2.  **Asynchronous Operations**: All I/O-bound operations (e.g., network requests, file I/O) must be asynchronous, using `asyncio`.
3.  **UI Layout**: The UI must be built using Toga's layout widgets (`toga.Box`, `toga.Pack`, etc.). Avoid using fixed-size widgets or absolute positioning.
4.  **Styling**: Use Toga's styling capabilities to create a visually appealing and accessible user interface.
5.  **Briefcase**: The application must be deployable using `briefcase`. The `pyproject.toml` file should be configured correctly for Briefcase.

## 4. Web Research

Extensive web research is required to ensure that the migration is following the latest best practices and that the code is valid. The following resources should be consulted:

*   **BeeWare Documentation**: https://docs.beeware.org/
*   **Toga Documentation**: https://toga.readthedocs.io/
*   **Briefcase Documentation**: https://briefcase.readthedocs.io/
*   **Pytest Documentation**: https://docs.pytest.org/
*   **Real Python**: https://realpython.com/
*   **Other relevant blogs and tutorials**

All information gathered from web research should be documented in the task details.

## 5. Code Quality and Documentation

The final codebase must be of high quality and well-documented. The following rules apply:

1.  **PEP 8**: All code must adhere to the PEP 8 style guide.
2.  **Type Hinting**: All functions and methods must have type hints.
3.  **Docstrings**: All modules, classes, functions, and methods must have docstrings that explain their purpose, arguments, and return values.
4.  **Comments**: Use comments to explain complex or non-obvious code.
5.  **Linting**: Use `ruff` and `mypy` to lint the code and ensure that it is free of errors.

By following these rules, we can ensure that the migration of AccessiWeather is a success.
