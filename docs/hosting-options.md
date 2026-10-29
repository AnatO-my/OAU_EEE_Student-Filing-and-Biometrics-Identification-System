# Hosting checkpoint — 21 October 2026

**29 October update:** The user has now authorized a Vercel demonstration if it
meets the $0/no-card constraint. See [Vercel demo preparation](vercel-demo.md) for
current payment evidence, configuration, checks and the pending account connection.
The older deferred status below describes the 21 October checkpoint.

**Deferred at the user's request. The active target is this Windows laptop.**
No hosting account was created, no cloud resource was provisioned, no repository
was published and no deployment or email delivery occurred during this work.
The files in `deployment/`, `Dockerfile` and `compose.production.yml` are prepared
templates; they are not evidence of a running hosted application. Docker is not
installed in the current execution environment, so images have not been built.

The budget remains **$0 with no card verification**. If hosting resumes, the most
promising option found was Northflank's Sandbox: its current pricing page lists
two free services with continuous compute, and its May 2026 guide explicitly
states no card is required. The proposed layout uses one web service containing
the React bundle, Caddy and Gunicorn, plus one email worker; Aiven remains the
database. Actual account eligibility, free build limits, private repository
access, certificate mounting and outbound Gmail connectivity still need proof.
Stop if the dashboard requests a card or selects a paid resource. This is a
candidate to validate, not a verified deployment.
[Northflank pricing](https://northflank.com/pricing),
[Northflank signup guide](https://northflank.com/blog/how-to-deploy-vibe-coded-v0-apps-to-production).

Other options researched do not currently establish the required complete
no-card deployment:

| Service | Relevant constraint | Decision |
| --- | --- | --- |
| Render Free | Sleeps after 15 idle minutes, blocks outbound SMTP 25/465/587, no free background workers. | Possible web preview with a separate local worker; cannot host this workflow unchanged. |
| Koyeb Free | One web instance, sleeps after one idle hour, cannot run a worker service. | Insufficient for independent continuous worker. |
| Railway Free | Recurring $1/month usage credit after the time-limited $5 trial; neither credit establishes enough capacity for continuous app and worker. | No claim of an unlimited free deployment. |
| PythonAnywhere Beginner | No always-on tasks; external access limited to approved HTTP(S) sites. | Does not fit direct Aiven PostgreSQL plus continuous worker. |
| Oracle Always Free | Most signups require phone/card; region capacity and idle reclamation apply. | Excluded by the no-card requirement. |

Sources checked on 21 October 2026:
[Render Free](https://render.com/docs/free),
[Koyeb instances](https://www.koyeb.com/docs/reference/instances),
[Railway plans](https://docs.railway.com/pricing/plans),
[Railway trial](https://docs.railway.com/pricing/free-trial),
[PythonAnywhere pricing](https://www.pythonanywhere.com/pricing/),
[Oracle Free Tier](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm),
[Oracle resource constraints](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm).

No card-based alternative should be provisioned to work around these limits.
Hosting remains deferred while local integration, concurrency and restoration
verification proceed.
