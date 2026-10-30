# Utility recommendation

## Summary

This analysis suggests that washing-machine demand may be suitable for
voluntary, non-billing customer feedback. The selected REFIT homes used their
washing machines most often around 10:00, and Saturday had the highest number
of detected cycle starts. Cycle duration and energy use varied between homes.

These results are useful for designing a pilot, but they are not population
estimates. The analysis covers only four UK households.

## Recommended opportunity

A utility could provide customers with simple advice about shifting flexible
laundry use away from a local peak-demand period. For example, a message could
suggest running a washing programme outside the peak window when the customer
has a time-of-use tariff or an automated appliance controller.

The service should describe the result as an estimate or general usage
pattern. It should not claim that the utility knows exactly when a washing
machine is operating.

The Part 3 model was tested on an unseen House 5. It estimated total
washing-machine energy with a 13.55% error, compared with 100% error for the
always-off baseline. Its active-state F1 score was 0.288, so it is suitable
for broad programme insights but not for billing or definitive event
detection.

## How to test the idea

The utility should run a controlled pilot with customers who have given
consent. Similar customers should be assigned randomly to either a feedback
group or a control group. The feedback group could receive washing-time or
off-peak guidance for eight to twelve weeks.

The evaluation should measure:

1. Washing-machine energy during the target peak period.
2. Total household energy consumption.
3. The number of programmes shifted outside the target period.
4. Customer engagement and complaints.

The changes in the feedback group should be compared with the control group.
A sample of model detections should also be checked using plug-level monitors
or customer diaries. The pilot should be considered successful only if it
reduces target peak-period energy without increasing total consumption or
causing unacceptable customer inconvenience.

## Limitations and responsible use

The model was developed using a small number of UK homes. Results may not
transfer directly to India because appliance types, voltage, household
routines, occupancy, climate, and tariff structures can differ.

Several appliances can produce similar aggregate signatures. Missing
intervals reduce the available evidence, and the pipeline does not invent
long outages. The cycle labels are based on practical thresholds rather than
independent ground truth. More households and a separate validation period
would be needed before deployment.

Appliance estimates should not be used for billing, disconnection,
enforcement, or sensitive conclusions about individual behaviour.

## Effect of lower-frequency meter data

With 15-minute or 30-minute readings, short washing-machine phases and pauses
would be averaged together. Cycle start and end times would become less
certain, and different appliance events could appear in the same interval.

Total energy and broad household load patterns could still be estimated.
However, event detection and precise customer feedback would be less reliable.
Fifteen-minute data may support broad time-of-use advice, while 30-minute data
would be more appropriate for population-level load-shape analysis than for
identifying individual appliance cycles.
