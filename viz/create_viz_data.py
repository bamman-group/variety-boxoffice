import csv
import json
from collections import defaultdict

by_year = defaultdict(list)
by_movie = {}  

with open("../data/variety_boxoffice_yearly.tsv") as f:

    reader = csv.reader(f, delimiter="\t")
    next(reader, None)  

    for row in reader:
        year, rank, imdb, box_office_str, title = row[0], row[1], row[2], row[3], row[4]
        genre = row[7] if len(row) > 7 else ""
        try:
            box_office = int(box_office_str)
        except ValueError:
            continue

        by_year[year].append({
            "rank": int(rank),
            "title": title,
            "imdb": imdb,
            "box_office": box_office,
            "genre": genre,
        })

        if imdb not in by_movie:
            by_movie[imdb] = {"title": title, "genre": genre}

for year in by_year:
    by_year[year].sort(key=lambda x: x["rank"])
    by_year[year] = by_year[year][:50]

top_imdbs = {m["imdb"] for movies in by_year.values() for m in movies}
by_movie = {k: v for k, v in by_movie.items() if k in top_imdbs}

weekly = defaultdict(list)

with open("../data/variety_boxoffice_weekly.tsv") as f:
    reader = csv.reader(f, delimiter="\t")
    next(reader, None)  

    for row in reader:
        imdb, date_str, gross_str = row[0], row[1], row[2]
        try:
            gross = float(gross_str)
        except ValueError:
            continue
        date_int = int(date_str.replace("-", ""))
        weekly[imdb].append([date_int, gross])

for imdb in weekly:
    weekly[imdb].sort(key=lambda x: x[0])

weekly = {k: v for k, v in weekly.items() if k in top_imdbs}

movie_list = sorted(
    [{"imdb": imdb, "title": d["title"], "genre": d["genre"]} for imdb, d in by_movie.items()],
    key=lambda x: x["title"].lower()
)

data = {
    "byYear": dict(by_year),
    "byMovie": by_movie,
    "weekly": dict(weekly),
    "movieList": movie_list,
    "years": sorted(by_year.keys()),
}

json_str = json.dumps(data, separators=(",", ":"))

with open("data.js", "w") as f:
    f.write(f"window.movieData={json_str};")

size_kb = len(json_str) // 1024
print(f"Years: {data['years'][0]} - {data['years'][-1]}")
print(f"Movies: {len(movie_list)}")
print(f"Weekly entries: {sum(len(v) for v in weekly.values())}")
print(f"data.js written ({size_kb} KB)")
