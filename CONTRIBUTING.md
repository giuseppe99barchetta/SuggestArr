# Contributing to Suggestarr

Thank you for considering contributing to this project! Here's how you can get started:

## How to Contribute:
- **Report Issues**: If you find bugs or issues, please open an issue on GitHub.
- **Suggest Features**: Have an idea for a new feature? We'd love to hear it! Open an issue with your proposal.
- **Submit Pull Requests**: If you want to fix a bug or implement a feature, feel free to submit a pull request. Please ensure your code follows the coding standards.
- **Improve Documentation**: You can contribute by improving this documentation or adding new sections to it.

## Guidelines:
1. Fork the repository and create your branch from `nightly`.
2. If you've added code that should be tested, add tests.
3. Ensure the code is well-documented.
4. Open a pull request and provide a clear explanation of the changes.

## Frontend Design System Rules (Required)

For all CSS and Vue `<style>` changes under `client/src`:

- Use design tokens from `client/src/assets/styles/variables.css`.
- Do **not** introduce hardcoded color values (`#hex`, `rgb/rgba`, `hsl/hsla`) in style declarations.
- Do **not** introduce hardcoded spacing values for `margin`, `padding`, or `gap`; use `var(--spacing-*)` (or `calc(...)` from tokens).
- Do **not** introduce hardcoded `border-radius`; use `var(--radius-*)` / component radius tokens.
- Do **not** introduce hardcoded `font-size`; use typography tokens (`var(--font-size-*)`, input/button font-size tokens).

### Advisory Linting (Warning-level)

The frontend includes warning-level style checks:

```bash
cd client && npm run lint:styles
```

This command is advisory-first (warning-level rules) to avoid breaking existing code while enforcing new contributions.

## Pull Request Checklist

- [ ] Tests added/updated when applicable
- [ ] Documentation updated when behavior or setup changed
- [ ] No hardcoded styles introduced

## Building the Docker Image
To build the Docker image for development, run the following commands:
```bash
docker build . -f ./docker/Dockerfile --target dev --tag suggestarr:nightly
```