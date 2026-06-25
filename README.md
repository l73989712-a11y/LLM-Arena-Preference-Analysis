# LLM Arena User Preference Analysis System

This is the portable Windows edition. It does not create a virtual environment.
Python packages are installed into the local `_packages` folder, so the project can run from any path, including folders whose names contain spaces.

## Quick start

1. Extract the ZIP completely.
2. Open the `LLM_Arena_Project_Portable` folder.
3. Double-click `RUN_SAMPLE_DEMO.bat`.

The script installs packages locally, builds sample results, and starts the Streamlit dashboard.

## Important

- Do not run files directly inside the ZIP preview.
- The project path does not need to be `C:\LLM_Arena_Project`.
- Your current Desktop path is supported.
- If installation is interrupted, run `RESET_PORTABLE_ENV.bat` and retry.

## Separate steps

- `00_CHECK_PYTHON.bat`
- `01_INSTALL_PORTABLE_PACKAGES.bat`
- `02_BUILD_SAMPLE_RESULTS.bat`
- `03_START_DASHBOARD.bat`

## Real data

Run `04_INSTALL_OPTIONAL_TOOLS.bat`, then `05_DOWNLOAD_REAL_DATA_AND_RUN.bat`.
