# REFIT Appliance Disaggregation

This project cleans raw REFIT electricity data, explores washing-machine use,
and estimates washing-machine power from whole-house measurements.

The analysis uses the official REFIT Electrical Load Measurements dataset from
the University of Strathclyde. Power is measured in watts. The original data
has an interval of approximately eight seconds and is converted to one-minute
mean values for this project.

## Project structure

The main folders and files are:

`data/raw/`

Contains the raw House 1 files used for Part 1.

`data/cleaned/CLEAN_REFIT_081116/`

Contains the official cleaned REFIT files used for Parts 2 and 3.

`src/`

Contains the reusable Python code for loading data, cleaning readings,
creating features, fitting the model, and calculating evaluation metrics.

`notebooks/01_raw_cleaning.ipynb`

Explains the raw House 1 inspection and cleaning process.

`notebooks/02_washer_eda.ipynb`

Explores washing-machine cycles across four households.

`notebooks/03_disaggregation.ipynb`

Trains and evaluates the washing-machine disaggregation model.

`outputs/`

Contains generated tables, figures, model results, and summaries.

## Installation

Open PowerShell in the project folder and create the virtual environment if it
does not already exist:

```powershell
python -m venv .venv
```

Activate it and install the required packages:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The notebooks should be run with the project virtual environment selected as
the Python kernel.

## Running the project

Run the notebooks in this order:

1. Open `notebooks/01_raw_cleaning.ipynb` and run all cells.
2. Open `notebooks/02_washer_eda.ipynb` and run all cells.
3. Open `notebooks/03_disaggregation.ipynb` and run all cells.

Part 1 can also be run from the project root:

```powershell
python src\cleaning.py
```

The notebooks use paths relative to the project folder. If a notebook is
opened from a different working directory, set the notebook working directory
to the project root before running it.

## Part 1: raw House 1 cleaning

Part 1 uses the two raw House 1 files in
`data/raw/REFIT_RAW_081116/`. It checks timestamps, ordering, duplicate
timestamps, missing values, irregular intervals, negative readings, and values
above 10,000 watts.

The pipeline sorts the readings, keeps the first row for duplicate
timestamps, resamples to one-minute means, and interpolates only internal gaps
of up to five minutes. Longer gaps remain missing and are flagged.

Part 1 writes:

`data/cleaned/house1_cleaned_1min.csv`

`data/cleaned/house1_raw_quality_report.json`

`data/cleaned/house1_cleaning_report.json`

`plots/house1_raw_vs_cleaned.png`

## Part 2: washing-machine exploratory analysis

Part 2 uses the official cleaned data for these households:

| House | Washing-machine channel |
|---:|:---|
| 1 | Appliance5 |
| 2 | Appliance2 |
| 3 | Appliance6 |
| 5 | Appliance3 |

Rows with `Issues == 1` are treated as unreliable. Gaps of up to three
minutes are interpolated, while longer gaps remain missing.

A cycle is considered active when washing-machine power is above 20 watts.
Pauses of up to ten minutes are merged into one cycle. Cycles shorter than ten
minutes or using less than 20 watt-hours are discarded.

Part 2 writes availability tables, cycle summaries, usage tables, and plots
to `outputs/`. The detailed findings are documented in
`RESULTS.md`.

## Part 3: disaggregation model

Part 3 estimates one-minute washing-machine power from the household
aggregate signal. Houses 1, 2, and 3 are used for training, and House 5 is
held out for testing. This household-level split prevents nearby windows from
the same home appearing in both training and testing.

The model is a `HistGradientBoostingRegressor`. It uses current and lagged
aggregate power, five-minute rolling statistics, hour of day, and day of
week. Predictions are clipped at zero watts.

The model is compared with an always-off baseline using:

MAE and RMSE for minute-level power error.

Total-energy error for overall consumption estimation.

Active precision, recall, and F1 for washing-machine activity detection.

Part 3 writes:

`outputs/disaggregation_model_results.csv`

`outputs/disaggregation_data_summary.csv`

`outputs/disaggregation_actual_vs_predicted.png`

## Part 4: practical recommendation

The utility-facing recommendation is in
`Recommendation.md`. It proposes an opt-in, non-billing feedback pilot for
shifting flexible laundry demand away from peak periods.

It also explains how to measure impact using a control group, why the model
should not be used for billing, limitations when applying UK results to India,
and what becomes harder when only 15-minute or 30-minute meter readings are
available.

## Documentation

`DATA.md` describes the dataset, data-quality checks, and cleaning decisions.

`RESULTS.md` contains the Part 2 findings, Part 3 evaluation results, plots,
failure cases, and practical implications.

`Recommendation.md` contains the utility-facing summary.

## Main limitations

The analysis covers only four UK households and uses appliance channels from
the official cleaned data. Aggregate power can contain overlapping signatures
from several appliances, so a washing-machine estimate is not guaranteed to
be correct for every minute.

The cycle thresholds are practical rules rather than independent ground truth.
Long missing intervals are not filled. Results should therefore be treated as
a reproducible case study and not as a universal description of household
washing-machine behaviour.
