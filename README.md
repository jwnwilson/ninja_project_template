# {{project_slug}}_be Project

This is a python hexagonal project that is compatible with the hextech monorepo.

This is not intended to be used standalone and is separete to facilitate "copier"s update functionality that relies on using git to create a diff if this template is updated to update existing projects.

## Testing

The project is configured to run tests in parallel using pytest-xdist for improved performance.

### Running Tests

- **Parallel tests (default)**: `make test` - Automatically detects CPU cores and runs tests in parallel

### Parallel Testing Configuration

- Tests use pytest-xdist with `-n auto` to automatically determine the number of workers
- Each worker process gets its own SQLite database to avoid conflicts
- Coverage data is combined from all worker processes automatically
