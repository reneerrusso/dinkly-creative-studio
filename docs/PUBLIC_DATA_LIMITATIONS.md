# Public Data Limitations

## Access and completeness

Public availability does not guarantee stable API access, complete metrics, reuse permission, or accurate provider extraction. Instagram, TikTok, providers, and individual accounts can change fields or access at any time. A missing count is not zero. A visible count can also be delayed, rounded, or later revised.

The system records only supplied or provider-returned fields and reports metric completeness. It does not infer shares from likes, views from followers, or posting dates from IDs.

## Comparability

Different platforms define and expose views, plays, shares, saves, and completion differently. Even within one platform, formats and account sizes can make raw totals incomparable. The agent therefore favors within-handle medians, averages, percentiles, and multipliers with sample size shown.

Those baselines are descriptive. A 2× median post is a standout within the collected sample, not proof that its topic caused performance or that DINKLY will match it.

## Snapshot and velocity limits

A metric snapshot is an observation at collection time. Velocity requires at least two snapshots with valid timestamps and a positive interval. It is unavailable for a single snapshot. Deleted or hidden posts can make later observations incomplete.

## Creative visibility

Caption, hashtags, audio name, and media type do not fully describe a comic or video. The default classifier may identify a caption-derived topic at Low confidence but cannot claim visual observations it did not receive. Human classification should state its source. A future configured model must record its method and uncertainty.

## Ethics and rights

The application is for public-performance research and original creative development. It does not bypass authentication, access private profiles, download protected media, or grant rights to reproduce posts. Respect platform terms, contracts, privacy, copyright, trademarks, publicity rights, and regional rules.

Store only what the team needs. Prefer public post URLs and compact normalized metadata over copied media. Remove monitoring when it is no longer necessary; retain or delete historical evidence according to the team’s policy and legal obligations.

## Reporting language

Use:

- “The collected record shows…” for measured facts.
- “The supplied classification identifies…” for human or model labels.
- “This may suggest…” for hypotheses.
- “Test an original DINKLY version of the principle…” for recommendations.

Avoid “proved,” “caused,” “guarantees,” “the algorithm prefers,” or precise forecasts unless a separate rigorous study supports them.

## Data-quality checklist

Before approving a learning, confirm platform, post ID, handle, timestamp source, metric completeness, snapshot count, sample size, baseline method, classification provenance, evidence IDs, hypothesis language, and a written limitation. If any material element is absent, lower confidence or leave the learning pending.
