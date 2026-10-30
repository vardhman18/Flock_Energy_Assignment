# Data and cleaning notes

## Dataset

This project uses the REFIT Electrical Load Measurements dataset from the
University of Strathclyde. REFIT contains whole-home electricity readings and
separate readings for selected appliances in 20 UK homes.

The power values are treated as watts. The original measurements were recorded
at approximately eight-second intervals. The analysis in this project converts
the readings to one-minute mean values.

The raw files used for Part 1 are stored in:

`data/raw/REFIT_RAW_081116/`

Part 1 uses House 1, which is split across these two files:

`RAW_House1_Part1.csv`

`RAW_House1_Part2.csv`

The official cleaned files used for Parts 2 and 3 are stored in:

`data/cleaned/CLEAN_REFIT_081116/`

The cleaned files contain the following important columns:

`Time`, `Unix`, `Aggregate`, `Appliance1` to `Appliance9`, and `Issues`.

`Aggregate` is the whole-house power reading. The appliance columns contain
the readings for individual circuits or appliances. The `Issues` column is a
quality flag from the official REFIT cleaning process. The documentation
describes `Issues == 1` as a row where the sum of the appliance readings is
greater than the aggregate reading.

## Part 1: raw House 1 inspection

The two raw House 1 files are loaded together. The `Time` column is parsed as
the timestamp because it is convenient for sorting, checking time intervals,
and resampling.

The inspection records:

- total number of rows
- invalid or missing timestamps
- duplicate timestamps
- earliest and latest timestamps
- intervals between consecutive readings
- missing values in each column
- negative power readings
- readings above 10,000 watts

The inspection report is saved as:

`data/cleaned/house1_raw_quality_report.json`

These checks are completed before cleaning so that the original data quality
can be compared with the cleaned output.

## Part 1: cleaning decisions

The cleaning pipeline follows a small number of explicit rules.

First, rows with invalid timestamps are removed. The remaining readings are
sorted in chronological order. If a timestamp appears more than once, the
first reading is kept. This rule is simple, deterministic, and avoids giving
duplicate records extra influence.

Values below zero watts or above 10,000 watts are treated as invalid and
replaced with missing values. They are not changed to zero because that would
hide the data-quality problem.

The readings are then resampled to one-minute intervals using the arithmetic
mean of the readings available in each minute.

Internal gaps of up to five minutes are filled using time-based interpolation.
Longer gaps are left missing because filling a long outage would create
unjustified artificial readings. These longer gaps are marked with the
`long_gap_missing` flag.

The cleaned file contains three quality flags:

`observed` means that the minute contains usable readings and no interpolation
was required.

`short_gap_filled` means that at least one value was filled by interpolation.

`long_gap_missing` means that at least one required channel is still missing.

The Part 1 outputs are:

`data/cleaned/house1_cleaned_1min.csv`

`data/cleaned/house1_cleaning_report.json`

`plots/house1_raw_vs_cleaned.png`

This is an intentionally manageable cleaning process. It covers the main
timestamp, duplicate, outlier, resampling, and missing-data issues without
claiming to reproduce every specialised correction in the official REFIT
pipeline.

## Parts 2 and 3: selected households

The washing-machine analysis uses four homes for which the cleaned REFIT
documentation identifies a washing-machine channel:

| House | Washing-machine channel |
|---:|:---|
| 1 | Appliance5 |
| 2 | Appliance2 |
| 3 | Appliance6 |
| 5 | Appliance3 |

The selected files cover approximately September 2013 to July 2015. The exact
start and end times after resampling are written to
`outputs/disaggregation_data_summary.csv` and
`outputs/washer_availability.csv`.

For Parts 2 and 3, rows with `Issues == 1` are treated as unreliable. The
aggregate and washing-machine readings in those rows are set to missing before
resampling. Gaps of up to three minutes are interpolated. Longer gaps remain
missing and are excluded from model feature construction.

Part 2 identifies a washing-machine cycle when power is above 20 watts. Pauses
of up to ten minutes are merged into the same cycle. Candidate cycles shorter
than ten minutes or using less than 20 watt-hours are discarded. These are
practical analysis thresholds rather than independent ground-truth labels.

Part 3 trains on Houses 1, 2, and 3 and evaluates on the unseen House 5. This
household-level split avoids mixing nearby windows from the same home between
training and testing.

## Remaining data limitations

The official cleaned data is not a perfect ground-truth record. Some values
have already been corrected or filled by the dataset creators, and the
`Issues` flag identifies only one type of inconsistency. The washing-machine
channel may not capture every appliance state perfectly.

The selected sample contains only four UK households. Appliance models,
household routines, electrical systems, climate, and tariff structures may be
different in India or in other populations. Results should therefore be
interpreted as a reproducible case study rather than a universal description
of washing-machine use.
