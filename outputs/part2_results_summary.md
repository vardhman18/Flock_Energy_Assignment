## Part 2 summary

I analysed Houses 1, 2, 3, 5 using the official cleaned REFIT files. The washing-machine channels were House 1: Appliance5, House 2: Appliance2, House 3: Appliance6, House 5: Appliance3. Readings were converted to one-minute means. Rows with Issues equal to 1 were treated as unreliable, gaps up to 3 minutes were interpolated, and longer gaps were retained as missing.

A cycle was defined as washer power above 20 W. Pauses of up to 10 minutes were merged into the same cycle. Cycles shorter than 10 minutes or below 20 Wh were discarded. Across the selected homes, the most common cycle-start hour was 10:00 and the most common start day was Saturday. The median detected cycle duration was 56.0 minutes and the median cycle energy was 352.2 Wh.

The 24-hour trace shows that washer activity is intermittent and is embedded within the larger aggregate household signal. The cycle zoom demonstrates that the threshold-and-pause rule identifies a plausible operating episode while allowing short low-power pauses. Cross-house box plots show household differences in cycle duration, peak power, and energy, so a model trained on one household should not automatically be assumed to represent another.
