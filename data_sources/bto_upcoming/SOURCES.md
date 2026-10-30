# Upcoming BTO projects (HDB), read 2026-10-30

HDB's Flat Portal (https://homes.hdb.gov.sg/home/landing) says "The next sales exercise will be held in November 2026" and lists 7 upcoming projects.
Each project has a small XML file at https://resource.homes.hdb.gov.sg/2026-06/upcoming-bto/<code>/2026-06_UPB_<base64 of code and number>.xml
with town, latitude, longitude, flat types, total units and a launch quarter (2026-10 in the files, older than the portal's November date).

HDB's server returns 403 to scripted requests, so the files were read once in a browser and copied by hand into upcoming_2026-11.csv (kept in Git, outside the ignored data/ folder). The CSV holds only
what the files say: no names, prices, waiting times or categories exist yet. Coordinates are HDB's own, the site position is indicative.
Re-read the portal after HDB's launch press release (Annex A) and replace these rows with the launched projects.
