# variety-boxoffice
Weekly box office earnings extracted from Variety magazine, 1922-1979

## Summary

This repository provides data extracted from Variety magazine, capturing weekly box office earnings within the US over the period 1922-1979. This research is decribed in the following article:

David Bamman, Kent Chang, Allison Cooper, Juishan Hsu, Reina Kushihashi, Madison Mar, Arnav Podichetty, Rachael Samberg, Ipek Sancak and Yuhan Shao (2026), TITLE, ArXiV.



## Data

`data/all_data.json`: All data extracted from Variety, organized by issue (in format: Year-Month-Date-PageNumber). Each issue contains a list of extractions, where each extraction contains the following information:

* Theater name
* City
* Movie title
* Week reported ("this week" or "last week")
* Gross earnings reported

`data/citymap.csv`: All cities mentioned in `all_data`, along with latitude/longitude and country (weekly/yearly ranks use US only)

`data/title_map.json`: Dictionary mapping movie name (as it appears in Variety) and year to likely IMDB ID. (e.g. "Gone with the Wind", "Gone" and "Gone with Wind" in 1940 are all mapped to IMDB ID tt0031381).

`data/variety_boxoffice_weekly.tsv`: Weekly box office totals per (IMDB) movie (created by `scripts/get_weekly.py`)

`data/variety_boxoffice_yearly.tsv`: Yearly box office totals per (IMDB) movie (created by `scripts/get_yearly.py`)


## Generate weekly and yearly ranks
```
gunzip data/all_data.json.gz
cd scripts
wget https://datasets.imdbws.com/title.basics.tsv.gz
gunzip title.basics.tsv.gz
python get_yearly.py > ../data/variety_boxoffice_yearly.tsv
python get_weekly.py > ../data/variety_boxoffice_weekly.tsv

```

## Visualization

`viz` contains HTML/js code to visualize the top 50 movies per year, including the distribution of their weekly earnings over time. (See, for instance, the cycle of re-releases for movies like <em>Gone with the Wind</em> and <em>Snow White</em>.)




