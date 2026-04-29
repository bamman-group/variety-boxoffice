import sys, json, glob, csv
from collections import Counter

countries={}
def read_cities(filename):
	with open(filename, newline="", encoding="utf-8") as f:
		reader = csv.DictReader(f)
		for row in reader:
			city=row["original"]
			country=row["country"]

			if len(country) == 0:
				continue

			countries[city]=country

read_cities("../data/citymap.csv")		


def get_aliases(filename):
	with open(filename) as file:
		data=json.load(file)
		return data

def proc(filename):

	path="../data/title_map.json" 
	mapper=get_aliases(path)

	
	weeks={}

	with open(filename) as file:
		data=json.load(file)

		for year in data:
		
			for page in data[year]:

				date = "-".join(page.split("-")[:3])

				if date not in weeks:
					weeks[date]=Counter()


				theater_total=Counter()

				for d in data[year][page]:

					movie=d["movie"]
					orig=movie
					gross=d["gross"]
					week=d["week"]

					if week != "last week":
						continue

					theater=d["theater"]
					city=d["city"]
					theater_city="%s_%s" % (theater, city)

					theater_total[theater_city]+=1

				for d in data[year][page]:

					movie=d["movie"]
					orig=movie
					gross=d["gross"]
					week=d["week"]

					if week != "last week":
						continue

					theater=d["theater"]
					city=d["city"]

					if theater.startswith("SHOWCASE") and city == "Hollywood":
						# these are manually verified as national grosses
						# 17060837.0 Star Trek SHOWCASE:857 Hollywood /data/dbamman/variety/model_output/preds/pro3_ultra_high_preds/1979-12-19-3.jsonl
						# 4758631.0 Alien SHOWCASE:91 Hollywood /data/dbamman/variety/model_output/preds/pro3_ultra_high_preds/1979-06-06-33.jsonl
						continue

					theater_city="%s_%s" % (theater, city)

					if movie in mapper[str(year)]:
						imdb=mapper[str(year)][movie]

						if not imdb.startswith("tt"):
							# None etc.
							continue

						if gross is not None:

							if gross > 0:

								if city not in countries:
									print(city, "not in countries -- ERROR")
									sys.exit(1)

								country=countries[city]
								# only get numbers for cities in the US
								
								if country == "USA":
									# if a theater plays multiple movies in one week, divide the report gross by the number of movies showing
									# (since we get the same gross for all movies)

									weeks[date][imdb]+=(gross/theater_total[theater_city])
				
				

	print('\t'.join(["imdb", "date", "box_office"]))

	for date in weeks:
		for imdb in weeks[date]:
			print("%s\t%s\t%s" % (imdb, date, weeks[date][imdb]))


proc("../data/all_data.json")
				