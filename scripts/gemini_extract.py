import os, sys, json, glob, re, time
from google import genai
from pydantic import BaseModel, Field
from typing import List

from google.genai.types import (
	FunctionDeclaration,
	GenerateContentConfig,
	GoogleSearch,
	HarmBlockThreshold,
	HarmCategory,
	MediaResolution,
	Part,
	Retrieval,
	SafetySetting,
	Tool,
	ToolCodeExecution,
	VertexAISearch,
)
from google.genai import types



class Tuple(BaseModel):
	theater: str = Field(description="The theater where the movie was playing")
	city: str = Field(description="The city where the movie was playing")
	movie: str = Field(description="The name of the movie")
	conf: str = Field(description="Model confidence in the accuracy of the extraction")
	week: str = Field(description="The week the box office gross numbers are reported for; choose 'last week', 'this week', or 'next week'")
	gross: int = Field(description="The box office dollar amount reported for that week")
	
class OutputFormat(BaseModel):

	results: List[Tuple]

# you need to fill in this info
PROJECT_ID = YOUR_PROJECT_ID
LOCATION = YOUR_LOCATION
client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

# path to first shot (page 7 of 5/11/1927 issue of Variety)
shotFile1="1927-05-11_7-1.jpg"

# path to second shot (page 11 of 3/15/1939 issue of Variety)
shotFile2="1939-03-15_11-1.jpg"

# path to jpgs to extract info from (one per page)
INPUT_DIR="jpgs"

# path to output directory (to write json files to)
outdir="predictions"
os.makedirs(outdir, exist_ok=True)


MODEL_ID = "gemini-3-pro-preview"


prompt1="""

The following image contains a page from a newspaper describing movie box office grosses at specific theaters in cities.  OCR the text and extract this information into structured json.  Each paragraph will generally describe the movies playing at one theater. For each movie you identify, you should extract the theater and city where it is playing, the box office dollar amount reported, and the week that the box office grosses apply to.  For the week, you should choose between "this week", "last week" or "next week".


Here's one example of an input/output pair:

Input:

New York, Oct. 7
"Pantages (Pan) (2,812; 30-40-55)— 'Honest Man', (U) (2d wk.). Holdover with new supporting feature looks good for $6,200, after corking $12,000 first week. 'Love Affair' (RKO) follows."

Output:

{
	"results": [
		{
			"theater": "Pantages",
			"movie": "Honest Man",
			"city": "New York",
			"conf": "high",
			"week": "this week"
			"gross": 6200
		},

		 {
			"theater": "Pantages",
			"movie": "Honest Man",
			"city": "New York",
			"conf": "high",
			"week": "last week"
			"gross": 12000 
		},  

		  {
			"theater": "Pantages",
			"movie": "Love Affair",
			"city": "New York",
			"conf": "high",
			"week": "next week"
			"gross": null
		},             
		
		]
 }

Here, the movie "Honest Man" is described as making $6,200 this week (its "2d wk" of playing).  The phrase "after corking $12,000 first week" tells us that it earned $12,000 during its first week of playing (last week).  We should extract 6200 for the gross value of movie "Honest Man" for week "this week" and 12000 as the gross value for the week value "last week". "Love Affair" is a movie that is also mentioned; the description says it "follows", meaning that it will play "next week"; we should extract that as well.


Here is how to figure out the value for "week":

-- If the page contains the phrase "Estimates for Last Week" then the "week" value will almost always be "last week"
-- If the page contains the phrase "Estimates for This Week", then every paragraph may report information about movies playing this week and last week.  Movies playing this week will usually show up at the beginning of the paragraph; movies playing last week will usually show up at the end of the paragraph.  If you see the phrase "last week" in a paragraph, then the movies appearing after that phrase will usually have played last week.

Sometimes a box office number is reported for multiple movies (this happens if a theater plays multiple movies in one week); you should create a separate tuple for each movie and report the original box office number for each of them (along with the week it played)

City information will generally appear at the start of a column in the form: City, Date (such as "San Francisco, Nov. 3") and apply to the theaters reported in the column under it. But the city can also be sometimes inferred from the title of a column (e.g., "B'WAY TUMBLED OFF LAST WEEK"). "Broadway" generally refers to New York.

You should also report your confidence in the extraction as high, medium, or low; your confidence may be low if the OCR quality is poor, or if there is ambiguity about whether the extraction is faithful to the text. Movie names will generally be contained within quotation marks -- double quotes ("movie name") or single quotes ('movie name').  

You should only extract movie/theater/city/week/gross tuples that appear on the page.  Do not extract information that appears in tables. You should ignore information about vaudeville shows, stage shows and orchestras (and only report information about movies).  Pages that have "LEGITIMATE" in the header are likely mostly about theater shows, not movies; pages with "PICTURES" and "PICTURE GROSSES" in the header will mostly reference movies.

Movies might appear under a "SHOWCASE" header in a column. If a movie is featured in a "Showcase" (where the total box office amount is reported for multiple theaters and the theaters are usually not named), you should set "SHOWCASE:N" to be the "theater" value you output, where N is the number of theaters (or "houses") you see reported.  Showcases can be reported for "this week", "last week", and "next week" and you should pay attention to that information as well so that you can output it correctly.

You should report the movie/theater/city/gross value as it appears *verbatim* on the page. Use your thinking budget to confirm that you are not hallucinating information that does not exist, and that the "week" values you have assigned for the movies and box office gross amounts are correct.



Here are a few more examples.

Input:

Broadway, Nov. 7
Estimates for Last Week 
Astor—“Big Parade” (M-G) (1,120; $1-$2) (77th week). Hasn’t tired yet in face of entrance of warm weather and money tightening up; no thought of picture to follow at this time; long-run leader easing along at $15,426. 

Cameo—“Flesh and Blood” (Com.) stand off general slump; $4,707; currently playing John Gilbert again, this time in “The Snob.” 

Output:

{
	"results": [
		{
			"theater": "Astor",
			"movie": "Big Parade",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 15426
		},

		{
			"theater": "Cameo",
			"movie": "Flesh and Blood",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 4707
		},              

		{
			"theater": "Cameo",
			"movie": "The Snob",
			"city": "New York",
			"conf": "high",
			"week": "this week",
			"gross": null
		}, 

		]
 }


Rationale:

"Broadway" as a location means "New York".  Otherwise this case is straightforward. "Estimates for Last Week" denotes that the box office numbers are from "last week", not "this week".  The text says that "The Snob" is "currently playing" at the Cameo, so its value should be "this week" and there is no box office gross to report for that movie.


Input:

Boston, Jan 10
SHOWCASE

“Close Encounters of Third
Kind” (Col), 7 houses (4th wk).
Looks mighty $300,000. Third week
was $350,000; second week, $275,000.

"Aces High" (Cinema Shares) (5 
theatres, 2,540 seats, $3) - Dismal
$5,500.


Output:

{
	"results": [
		{
			"theater": "SHOWCASE:7",
			"movie": "Close Encounters of Third Kind",
			"city": "Boston",
			"conf": "high",
			"week": "this week",
			"gross": 300000
		},
		{
			"theater": "SHOWCASE:7",
			"movie": "Close Encounters of Third Kind",
			"city": "Boston",
			"conf": "high",
			"week": "last week",
			"gross": 350000
		},    
		{
			"theater": "SHOWCASE:5",
			"movie": "Aces High",
			"city": "Boston",
			"conf": "high",
			"week": "this week",
			"gross": 5500
		}, 


		]
 }


Rationale:

The "SHOWCASE" header in the column signals that what follows is a showcase, and the format puts the movie at the beginning of the paragraph.  For "Close Encounters of Third Kind", the showcase reports $300,000 estimated for this week from 7 theaters, and $350,000 is reported for the same 7 theaters last week.  For "Aces High" the showcase repots $5,500 estimated for the current week in 5 theaters.



Input:

Topeka, Jan. 3
Estimates for Last Week 
Jayhawk (1,500; 40) (Jayhawk theater Corp.). Week’s dancing programs staged by local school brought out papas and mamas. Above normal. “McFadden’s Flats” the first four days and “See You In Jail” the last two. Slightly over $3,400.


Output:

{
	"results": [
		{
			"theater": "Jayhawk",
			"movie": "McFadden’s Flats",
			"city": "Topeka",
			"conf": "high",
			"week": "last week",
			"gross": 3400
		},
		{
			"theater": "Jayhawk",
			"movie": "See You In Jail",
			"city": "Topeka",
			"conf": "high",
			"week": "last week",
			"gross": 3400
		},              
		]
 }

Rationale:

"Estimates for Last Week" denotes that the box office numbers are from "last week", not "this week".  There are two movies described, both playing at the same theater during the same week.  Both movies together made $3,400, so we should report that number for each movie separately.


Input:

Cincinnati, Nov. 13
Estimates for This Week 
Family (RKO) (1,000; 20–30)—
Homicide Bureau (Col) and Long Shot (GN), split with White Woman (Ind) and Miss X (Rep).
Average $2,200. Same last week for Pirates Skies (U) and Am Criminal (Mono), split with Boy Slaves (RKO) and Home on Prairie (Rep).

Output:

{
	"results": [
	 {
			"theater": "Family",
			"movie": "Homicide Bureau",
			"city": "Cincinnati",
			"conf": "medium",
			"week": "this week",
			"gross": 2200
		},

	  {
			"theater": "Family",
			"movie": "Long Shot",
			"city": "Cincinnati",
			"conf": "medium",
			"week": "this week",
			"gross": 2200
		},

	  {
			"theater": "Family",
			"movie": "White Woman",
			"city": "Cincinnati",
			"conf": "medium",
			"week": "this week",
			"gross": 2200
		},

	  {
			"theater": "Family",
			"movie": "Miss X",
			"city": "Cincinnati",
			"conf": "medium",
			"week": "this week",
			"gross": 2200
		}, 

		{
			"theater": "Family",
			"movie": "Pirates Skies",
			"city": "Cincinnati",
			"conf": "medium",
			"week": "last week",
			"gross": 2200
		},

	  {
			"theater": "Family",
			"movie": "Am Criminal",
			"city": "Cincinnati",
			"conf": "medium",
			"week": "last week",
			"gross": 2200
		},

	  {
			"theater": "Family",
			"movie": "Boy Slaves",
			"city": "Cincinnati",
			"conf": "medium",
			"week": "last week",
			"gross": 2200
		},

	  {
			"theater": "Family",
			"movie": "Home on Prairie",
			"city": "Cincinnati",
			"conf": "medium",
			"week": "last week",
			"gross": 2200
		},                

		]
 }

Rationale:

"Estimates for This Week" tells us that the focus will first be on the movies playing "this week".
Homicide Bureau, Long Shot, White Woman and Miss X are all reported as currently playing this week, with an average box office of $2,200, so you should extract them with the week value "this week".  We need to pay attention to the parts where "last week" is mentioned. Four movies were playing last week (Pirates Skies, Am Criminal, Boy Slaves, and Home on Prairie), and they made the same as the number reported for a different set of movies this week ($2,200), so you should extract them with the week value "last week".  


Input:

Louisville, Feb. 6
Estimates for This Week 
Mary Anderson (Libson) (1,000; 15–30–40)—Darling Daughter (WB) (2d wk).
H.o. stanza still showing a profit, with wind-up figure around the $3,500 mark, okay.
Last week, same film tallied okay $5,500. No hints of censorship and the like here, which might have helped to build it bigger.


Output:

{
	"results": [
		{
			"theater": "Mary Anderson",
			"movie": "Darling Daughter",
			"city": "Louisville",
			"conf": "medium",
			"week": "this week",
			"gross": 3500
		},
			
		{
			"theater": "Mary Anderson",
			"movie": "Darling Daughter",
			"city": "Louisville",
			"conf": "medium",
			"week": "last week",
			"gross": 5500
		},
			  
		]
 }


Rationale:

"Estimates for This Week" tells us that the focus will first be on the movies playing "this week". "Darling Daughter" is currently playing and has a box office number of $3,500 for the current week so we should extract that with week value "this week".  The text says "Last week, same film tallied okay $5,500." -- which tells us that "Darling Daughter" also showed last week, and grossed $5,500.  We should extract that with week value "last week".



Input:

San Francisco, Nov. 1
St. Francis (F-WC) (1,470; 35–55–75)—Pygmalion (M-G) (4th wk).
One of the sweetest money makers in town, this picture has been able to buck the Fair and the weather.
Fourth session headed for $6,000, which is just about as healthy as last week.


Output:

{
	"results": [
		{
			"theater": "St. Francis",
			"movie": "Pygmalion",
			"city": "San Francisco",
			"week": "this week",
			"conf": "medium",
			"gross": 6000
		},
		{
			"theater": "St. Francis",
			"movie": "Pygmalion",
			"city": "San Francisco",
			"week": "last week",
			"conf": "medium",
			"gross": 6000
		},
			  
		]
 }

Rationale:

We don't see "Estimates for Last Week" mentioned, so we need to pay attention to where "last week" shows up to extract the numbers reported for last week and this week. "Pygmalion" has a box office number headed for $6,000 for the current week (so we should extract that with week value "this week"). "Fourth session headed for $6,000, which is just about as healthy as last week" tells us that "Pygmalion" also showed last week, and grossed around $6,000 then as well (so we should extract that with week value "last week").


	Here are two examples of complete input/output pairs.


Input image:


"""

prompt2="""

Output json:

{
	"grosses_in_header": false,
	"results": [

		{
			"theater": "Chicago",
			"movie": "Evening Clothes",
			"city": "Chicago",
			"conf": "high",
			"week": "last week",
			"gross": 60000
		},
		{
			"theater": "McVicker's",
			"movie": "Slide, Kelly, Slide",
			"city": "Chicago",
			"conf": "high",
			"week": "last week",
			"gross": 15000
		},
		{
			"theater": "Monroe",
			"movie": "Hills of Peril",
			"city": "Chicago",
			"conf": "high",
			"week": "last week",
			"gross": 4200
		},
		{
			"theater": "Oriental",
			"movie": "Senorita",
			"city": "Chicago",
			"conf": "high",
			"week": "last week",
			"gross": 45000
		},
		{
			"theater": "Orpheum",
			"movie": "Yankee Clipper",
			"city": "Chicago",
			"conf": "high",
			"week": "next week",
			"gross": null
		},
		{
			"theater": "Orpheum",
			"movie": "Better 'Ole",
			"city": "Chicago",
			"conf": "high",
			"week": "last week",
			"gross": 7800
		},
		{
			"theater": "Randolph",
			"movie": "Monte Cristo",
			"city": "Chicago",
			"conf": "high",
			"week": "last week",
			"gross": 7400
		},
		{
			"theater": "Roosevelt",
			"movie": "Fire Brigade",
			"city": "Chicago",
			"conf": "high",
			"week": "last week",
			"gross": 11000
		},
		{
			"theater": "State-Lake",
			"movie": "No Control",
			"city": "Chicago",
			"conf": "high",
			"week": "last week",
			"gross": 17500
		},
		{
			"theater": "Auditorium",
			"movie": "Rough Riders",
			"city": "Chicago",
			"conf": "high",
			"week": "next week",
			"gross": null
		},
		{
			"theater": "Auditorium",
			"movie": "Old Ironsides",
			"city": "Chicago",
			"conf": "high",
			"week": "last week",
			"gross": 15000
		},        
		{
			"theater": "Alhambra",
			"movie": "Fashions for Women",
			"city": "Milwaukee",
			"conf": "high",
			"week": "last week",
			"gross": 16000
		},
		{
			"theater": "Davidson",
			"movie": "What Price Glory",
			"city": "Milwaukee",
			"conf": "high",
			"week": "last week",
			"gross": 11000
		},
		{
			"theater": "Garden",
			"movie": "Mother",
			"city": "Milwaukee",
			"conf": "high",
			"week": "last week",
			"gross": 3000
		},
		{
			"theater": "Majestic",
			"movie": "Play Safe",
			"city": "Milwaukee",
			"conf": "high",
			"week": "last week",
			"gross": 6200
		},
		{
			"theater": "Merrill",
			"movie": "The Demi-Bride",
			"city": "Milwaukee",
			"conf": "high",
			"week": "last week",
			"gross": 5100
		},
		{
			"theater": "Miller",
			"movie": "Fire Brigade",
			"city": "Milwaukee",
			"conf": "high",
			"week": "last week",
			"gross": 7200
		},
		{
			"theater": "Palace",
			"movie": "Little Adventurers",
			"city": "Milwaukee",
			"conf": "high",
			"week": "last week",
			"gross": 18000
		},
		{
			"theater": "Strand",
			"movie": "Telephone Girl",
			"city": "Milwaukee",
			"conf": "high",
			"week": "last week",
			"gross": 5000
		},
		{
			"theater": "Wisconsin",
			"movie": "Knockout Riley",
			"city": "Milwaukee",
			"conf": "high",
			"week": "last week",
			"gross": 16000
		},
		{
			"theater": "Astor",
			"movie": "Big Parade",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 15426
		},
		{
			"theater": "Cameo",
			"movie": "The Snob",
			"city": "New York",
			"conf": "high",
			"week": "this week",
			"gross": null
		},
		{
			"theater": "Cameo",
			"movie": "Flesh and Blood",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 4707
		},
		{
			"theater": "Capitol",
			"movie": "Venus of Venice",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 47459
		},
		{
			"theater": "Cohan",
			"movie": "Rough Riders",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 6370
		},
		{
			"theater": "Colony",
			"movie": "The Climbers",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 5774
		},
		{
			"theater": "Criterion",
			"movie": "Old Ironsides",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 7905
		},
		{
			"theater": "Embassy",
			"movie": "Annie Laurie",
			"city": "New York",
			"conf": "high",
			"week": "next week",
			"gross": null
		},
		{
			"theater": "Embassy",
			"movie": "Slide, Kelly, Slide",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 7872
		},
		{
			"theater": "Gaiety",
			"movie": "King of Kings",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 14532
		},
		{
			"theater": "Globe",
			"movie": "Camille",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 16354
		},
		{
			"theater": "Harris",
			"movie": "What Price Glory",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 12856
		},
		{
			"theater": "Paramount",
			"movie": "Cabaret",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 58000
		},
		{
			"theater": "Rialto",
			"movie": "Beau Geste",
			"city": "New York",
			"conf": "high",
			"week": "next week",
			"gross": null
		},
		{
			"theater": "Rialto",
			"movie": "Children of Divorce",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 16400
		},
		{
			"theater": "Rivoli",
			"movie": "Chang",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 30162
		},
		{
			"theater": "Roxy",
			"movie": "The Yankee Clipper",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 102153
		},
		{
			"theater": "Shubert-Teller",
			"movie": "What Price Glory",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 15875
		},
		{
			"theater": "Strand",
			"movie": "His First Flame",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 27300
		},
		{
			"theater": "Warners",
			"movie": "When a Man Loves",
			"city": "New York",
			"conf": "high",
			"week": "last week",
			"gross": 13735
		},
		{
			"theater": "Aldine",
			"movie": "Better 'Ole",
			"city": "Philadelphia",
			"conf": "high",
			"week": "next week",
			"gross": null
		},
		{
			"theater": "Aldine",
			"movie": "Don Juan",
			"city": "Philadelphia",
			"conf": "high",
			"week": "last week",
			"gross": 11000
		},
		{
			"theater": "Arcadia",
			"movie": "Venus of Venice",
			"city": "Philadelphia",
			"conf": "high",
			"week": "last week",
			"gross": 3500
		},
		{
			"theater": "Fox",
			"movie": "The Red Mill",
			"city": "Philadelphia",
			"conf": "high",
			"week": "last week",
			"gross": 25000
		},
		{
			"theater": "Fox-Locust",
			"movie": "What Price Glory",
			"city": "Philadelphia",
			"conf": "high",
			"week": "last week",
			"gross": 12000
		},
		{
			"theater": "Karlton",
			"movie": "Too Many Crooks",
			"city": "Philadelphia",
			"conf": "high",
			"week": "last week",
			"gross": 3000
		},
		{
			"theater": "Stanley",
			"movie": "Lovers",
			"city": "Philadelphia",
			"conf": "high",
			"week": "last week",
			"gross": 31000
		},
		{
			"theater": "Stanton",
			"movie": "The Fire Brigade",
			"city": "Philadelphia",
			"conf": "high",
			"week": "last week",
			"gross": 14000
		},
		{
			"theater": "California",
			"movie": "Whirlwind of Youth",
			"city": "San Francisco",
			"conf": "high",
			"week": "last week",
			"gross": 12200
		},
		{
			"theater": "Granada",
			"movie": "Children of Divorce",
			"city": "San Francisco",
			"conf": "high",
			"week": "last week",
			"gross": 21200
		},
		{
			"theater": "Loew's Warfield",
			"movie": "Mr Wu",
			"city": "San Francisco",
			"conf": "high",
			"week": "last week",
			"gross": 32000
		},
		{
			"theater": "St. Francis",
			"movie": "Night of Love",
			"city": "San Francisco",
			"conf": "high",
			"week": "last week",
			"gross": 11000
		},
		{
			"theater": "Cory",
			"movie": "Corporate Kate",
			"city": "Topeka",
			"conf": "high",
			"week": "last week",
			"gross": 750
		},
		{
			"theater": "Isis",
			"movie": "It",
			"city": "Topeka",
			"conf": "high",
			"week": "last week",
			"gross": 2200
		},
		{
			"theater": "Jayhawk",
			"movie": "McFadden's Flats",
			"city": "Topeka",
			"conf": "high",
			"week": "last week",
			"gross": 3400
		},
		{
			"theater": "Jayhawk",
			"movie": "See You In Jail",
			"city": "Topeka",
			"conf": "high",
			"week": "last week",
			"gross": 3400
		},
		{
			"theater": "Orpheum",
			"movie": "The Fire Brigade",
			"city": "Topeka",
			"conf": "high",
			"week": "last week",
			"gross": 2000
		}
	]
}


Input image:

"""

prompt3="""

Output json:

{
	"results": [
		{
			"theater": "Buffalo",
			"movie": "Wife, Husband",
			"city": "Buffalo",
			"conf": "high",
			"week": "this week",
			"gross": 20000
		},
		{
			"theater": "Buffalo",
			"movie": "Darling Daughter",
			"city": "Buffalo",
			"conf": "high",
			"week": "last week",
			"gross": 12000
		},
		{
			"theater": "Century",
			"movie": "St. Louis Blues",
			"city": "Buffalo",
			"conf": "high",
			"week": "this week",
			"gross": 7500
		},
		{
			"theater": "Century",
			"movie": "Boy Trouble",
			"city": "Buffalo",
			"conf": "high",
			"week": "this week",
			"gross": 7500
		},
		{
			"theater": "Century",
			"movie": "King Underworld",
			"city": "Buffalo",
			"conf": "high",
			"week": "last week",
			"gross": 7500
		},
		{
			"theater": "Century",
			"movie": "O'Connor",
			"city": "Buffalo",
			"conf": "high",
			"week": "last week",
			"gross": 7500
		},
		{
			"theater": "Great Lakes",
			"movie": "Stagecoach",
			"city": "Buffalo",
			"conf": "high",
			"week": "this week",
			"gross": 10000
		},
		{
			"theater": "Great Lakes",
			"movie": "Beachcomber",
			"city": "Buffalo",
			"conf": "high",
			"week": "last week",
			"gross": 9500
		},
		{
			"theater": "Hipp",
			"movie": "Three Musketeers",
			"city": "Buffalo",
			"conf": "high",
			"week": "this week",
			"gross": 7000
		},
		{
			"theater": "Hipp",
			"movie": "Pygmalion",
			"city": "Buffalo",
			"conf": "high",
			"week": "last week",
			"gross": 7000
		},
		{
			"theater": "Lafayette",
			"movie": "Let Live",
			"city": "Buffalo",
			"conf": "high",
			"week": "this week",
			"gross": 8500
		},
		{
			"theater": "Lafayette",
			"movie": "Flight to Fame",
			"city": "Buffalo",
			"conf": "high",
			"week": "this week",
			"gross": 8500
		},
		{
			"theater": "Lafayette",
			"movie": "Honest Man",
			"city": "Buffalo",
			"conf": "high",
			"week": "last week",
			"gross": 6000
		},
		{
			"theater": "Lafayette",
			"movie": "Stand Accused",
			"city": "Buffalo",
			"conf": "high",
			"week": "last week",
			"gross": 6000
		},
		{
			"theater": "Albee",
			"movie": "Cafe Society",
			"city": "Cincinnati",
			"conf": "high",
			"week": "this week",
			"gross": 10000
		},
		{
			"theater": "Albee",
			"movie": "Little Princess",
			"city": "Cincinnati",
			"conf": "high",
			"week": "last week",
			"gross": 11000
		},
		{
			"theater": "Capitol",
			"movie": "Little Princess",
			"city": "Cincinnati",
			"conf": "high",
			"week": "this week",
			"gross": 3500
		},
		{
			"theater": "Capitol",
			"movie": "Each Other",
			"city": "Cincinnati",
			"conf": "high",
			"week": "last week",
			"gross": 5000
		},
		{
			"theater": "Family",
			"movie": "Homicide Bureau",
			"city": "Cincinnati",
			"conf": "high",
			"week": "this week",
			"gross": 2200
		},
		{
			"theater": "Family",
			"movie": "Long Shot",
			"city": "Cincinnati",
			"conf": "high",
			"week": "this week",
			"gross": 2200
		},
		{
			"theater": "Family",
			"movie": "White Woman",
			"city": "Cincinnati",
			"conf": "high",
			"week": "this week",
			"gross": 2200
		},
		{
			"theater": "Family",
			"movie": "Miss X",
			"city": "Cincinnati",
			"conf": "high",
			"week": "this week",
			"gross": 2200
		},
		{
			"theater": "Family",
			"movie": "Pirates Skies",
			"city": "Cincinnati",
			"conf": "high",
			"week": "last week",
			"gross": 2200
		},
		{
			"theater": "Family",
			"movie": "Am Criminal",
			"city": "Cincinnati",
			"conf": "high",
			"week": "last week",
			"gross": 2200
		},
		{
			"theater": "Family",
			"movie": "Boy Slaves",
			"city": "Cincinnati",
			"conf": "high",
			"week": "last week",
			"gross": 2200
		},
		{
			"theater": "Family",
			"movie": "Home on Prairie",
			"city": "Cincinnati",
			"conf": "high",
			"week": "last week",
			"gross": 2200
		},
		{
			"theater": "Grand",
			"movie": "Each Other",
			"city": "Cincinnati",
			"conf": "high",
			"week": "this week",
			"gross": 2500
		},
		{
			"theater": "Grand",
			"movie": "Gunga Din",
			"city": "Cincinnati",
			"conf": "high",
			"week": "last week",
			"gross": 2800
		},
		{
			"theater": "Keith's",
			"movie": "St. Louis Blues",
			"city": "Cincinnati",
			"conf": "high",
			"week": "this week",
			"gross": 4500
		},
		{
			"theater": "Keith's",
			"movie": "Duke West Point",
			"city": "Cincinnati",
			"conf": "high",
			"week": "last week",
			"gross": 5000
		},
		{
			"theater": "Lyric",
			"movie": "Boy Trouble",
			"city": "Cincinnati",
			"conf": "high",
			"week": "this week",
			"gross": 2200
		},
		{
			"theater": "Lyric",
			"movie": "Persons in Hiding",
			"city": "Cincinnati",
			"conf": "high",
			"week": "last week",
			"gross": 2200
		},
		{
			"theater": "Palace",
			"movie": "Freedom Ring",
			"city": "Cincinnati",
			"conf": "high",
			"week": "this week",
			"gross": 8500
		},
		{
			"theater": "Palace",
			"movie": "Tail Spin",
			"city": "Cincinnati",
			"conf": "high",
			"week": "last week",
			"gross": 7000
		},
		{
			"theater": "Shubert",
			"movie": "Beachcomber",
			"city": "Cincinnati",
			"conf": "high",
			"week": "this week",
			"gross": 5000
		},
		{
			"theater": "Shubert",
			"movie": "Beachcomber",
			"city": "Cincinnati",
			"conf": "high",
			"week": "last week",
			"gross": 9500
		},
		{
			"theater": "Aladdin",
			"movie": "Wife, Husband",
			"city": "Denver",
			"conf": "high",
			"week": "this week",
			"gross": 3000
		},
		{
			"theater": "Aladdin",
			"movie": "Stagecoach",
			"city": "Denver",
			"conf": "high",
			"week": "last week",
			"gross": 4500
		},
		{
			"theater": "Broadway",
			"movie": "Fast and Loose",
			"city": "Denver",
			"conf": "high",
			"week": "this week",
			"gross": 2000
		},
		{
			"theater": "Broadway",
			"movie": "Four Girls",
			"city": "Denver",
			"conf": "high",
			"week": "this week",
			"gross": 2000
		},
		{
			"theater": "Broadway",
			"movie": "Huck Finn",
			"city": "Denver",
			"conf": "high",
			"week": "last week",
			"gross": 3500
		},
		{
			"theater": "Broadway",
			"movie": "Pacific Liner",
			"city": "Denver",
			"conf": "high",
			"week": "last week",
			"gross": 3500
		},
		{
			"theater": "Denham",
			"movie": "Eagle and Hawk",
			"city": "Denver",
			"conf": "high",
			"week": "this week",
			"gross": 8400
		},
		{
			"theater": "Denham",
			"movie": "Third of Nation",
			"city": "Denver",
			"conf": "high",
			"week": "last week",
			"gross": 6100
		},
		{
			"theater": "Denver",
			"movie": "Wings Navy",
			"city": "Denver",
			"conf": "high",
			"week": "this week",
			"gross": 8000
		},
		{
			"theater": "Denver",
			"movie": "Wife, Husband",
			"city": "Denver",
			"conf": "high",
			"week": "last week",
			"gross": 11000
		},
		{
			"theater": "Orpheum",
			"movie": "Pygmalion",
			"city": "Denver",
			"conf": "high",
			"week": "this week",
			"gross": 11000
		},
		{
			"theater": "Orpheum",
			"movie": "Boy Slaves",
			"city": "Denver",
			"conf": "high",
			"week": "this week",
			"gross": 11000
		},
		{
			"theater": "Orpheum",
			"movie": "Fast and Loose",
			"city": "Denver",
			"conf": "high",
			"week": "last week",
			"gross": 10000
		},
		{
			"theater": "Orpheum",
			"movie": "Four Girls",
			"city": "Denver",
			"conf": "high",
			"week": "last week",
			"gross": 10000
		},
		{
			"theater": "Paramount",
			"movie": "Made Me Criminal",
			"city": "Denver",
			"conf": "high",
			"week": "this week",
			"gross": 4000
		},
		{
			"theater": "Paramount",
			"movie": "Nancy Drew",
			"city": "Denver",
			"conf": "high",
			"week": "this week",
			"gross": 4000
		},
		{
			"theater": "Paramount",
			"movie": "Three Musketeers",
			"city": "Denver",
			"conf": "high",
			"week": "last week",
			"gross": 4000
		},
		{
			"theater": "Paramount",
			"movie": "New York Sleeps",
			"city": "Denver",
			"conf": "high",
			"week": "last week",
			"gross": 4000
		},
		{
			"theater": "Rialto",
			"movie": "Stage-coach",
			"city": "Denver",
			"conf": "high",
			"week": "this week",
			"gross": 3000
		},
		{
			"theater": "Rialto",
			"movie": "Moto's Warning",
			"city": "Denver",
			"conf": "high",
			"week": "this week",
			"gross": 3000
		},
		{
			"theater": "Chinese",
			"movie": "Stagecoach",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 10300
		},
		{
			"theater": "Chinese",
			"movie": "Inside Story",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 10300
		},
		{
			"theater": "Chinese",
			"movie": "Little Princess",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 10800
		},
		{
			"theater": "Chinese",
			"movie": "Girl Downstairs",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 10800
		},
		{
			"theater": "Downtown",
			"movie": "Secret Service",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 11000
		},
		{
			"theater": "Downtown",
			"movie": "Topper",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 11000
		},
		{
			"theater": "Downtown",
			"movie": "Duke West Point",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 6200
		},
		{
			"theater": "Downtown",
			"movie": "Nancy Drew",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 6200
		},
		{
			"theater": "Four Star",
			"movie": "Pygmalion",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 2500
		},
		{
			"theater": "Four Star",
			"movie": "Pygmalion",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 2900
		},
		{
			"theater": "Hollywood",
			"movie": "Topper",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 12000
		},
		{
			"theater": "Hollywood",
			"movie": "Secret Service",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 12000
		},
		{
			"theater": "Hollywood",
			"movie": "Duke West Point",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 5500
		},
		{
			"theater": "Hollywood",
			"movie": "Nancy Drew",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 5500
		},
		{
			"theater": "Orpheum",
			"movie": "Disbarred",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 6500
		},
		{
			"theater": "Orpheum",
			"movie": "Flirting Fate",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 6500
		},
		{
			"theater": "Orpheum",
			"movie": "Smiling Along",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 7000
		},
		{
			"theater": "Orpheum",
			"movie": "Gambling Ship",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 7000
		},
		{
			"theater": "Pantages",
			"movie": "Honest Man",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 6200
		},
		{
			"theater": "Pantages",
			"movie": "Wharf",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 6200
		},
		{
			"theater": "Pantages",
			"movie": "Honest Man",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 12000
		},
		{
			"theater": "Pantages",
			"movie": "Wharf",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 12000
		},
		{
			"theater": "Paramount",
			"movie": "Cafe Society",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 13000
		},
		{
			"theater": "Paramount",
			"movie": "St. Louis Blues",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 10500
		},
		{
			"theater": "RKO",
			"movie": "Honest Man",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 6800
		},
		{
			"theater": "RKO",
			"movie": "Warf",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 6800
		},
		{
			"theater": "RKO",
			"movie": "Honest Man",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 13200
		},
		{
			"theater": "RKO",
			"movie": "Wharf",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 13200
		},
		{
			"theater": "State",
			"movie": "Stagecoach",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 13500
		},
		{
			"theater": "State",
			"movie": "Inside Story",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 13500
		},
		{
			"theater": "State",
			"movie": "Little Princess",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 13200
		},
		{
			"theater": "State",
			"movie": "Girl Downstairs",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 13200
		},
		{
			"theater": "United Artists",
			"movie": "Little Princess",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 3500
		},
		{
			"theater": "United Artists",
			"movie": "Girl Downstairs",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 3500
		},
		{
			"theater": "United Artists",
			"movie": "Each Other",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 2700
		},
		{
			"theater": "United Artists",
			"movie": "Pardon Nerve",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 2700
		},
		{
			"theater": "Wilshire",
			"movie": "Little Princess",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 5100
		},
		{
			"theater": "Wilshire",
			"movie": "Girl Downstairs",
			"city": "Los Angeles",
			"conf": "high",
			"week": "this week",
			"gross": 5100
		},
		{
			"theater": "Wilshire",
			"movie": "Each Other",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 4700
		},
		{
			"theater": "Wilshire",
			"movie": "Pardon Nerve",
			"city": "Los Angeles",
			"conf": "high",
			"week": "last week",
			"gross": 4700
		},
		{
			"theater": "Brown",
			"movie": "Pygmalion",
			"city": "Louisville",
			"conf": "high",
			"week": "this week",
			"gross": 2400
		},
		{
			"theater": "Brown",
			"movie": "Son Criminal",
			"city": "Louisville",
			"conf": "high",
			"week": "this week",
			"gross": 2400
		},
		{
			"theater": "Brown",
			"movie": "Honest Man",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 1900
		},
		{
			"theater": "Brown",
			"movie": "Gambling Ship",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 1900
		},
		{
			"theater": "Kentucky",
			"movie": "Off Record",
			"city": "Louisville",
			"conf": "high",
			"week": "this week",
			"gross": 1900
		},
		{
			"theater": "Kentucky",
			"movie": "Paris Honeymoon",
			"city": "Louisville",
			"conf": "high",
			"week": "this week",
			"gross": 1900
		},
		{
			"theater": "Kentucky",
			"movie": "Dawn Patrol",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 1500
		},
		{
			"theater": "Kentucky",
			"movie": "Up River",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 1500
		},
		{
			"theater": "Kentucky",
			"movie": "Secrets of Nurse",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 1500
		},
		{
			"theater": "Kentucky",
			"movie": "Peck's Boy",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 1500
		},
		{
			"theater": "Loew's State",
			"movie": "Fast and Loose",
			"city": "Louisville",
			"conf": "high",
			"week": "this week",
			"gross": 6500
		},
		{
			"theater": "Loew's State",
			"movie": "Four Girls",
			"city": "Louisville",
			"conf": "high",
			"week": "this week",
			"gross": 6500
		},
		{
			"theater": "Loew's State",
			"movie": "Topper",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 5500
		},
		{
			"theater": "Loew's State",
			"movie": "Dr. Meade",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 5500
		},
		{
			"theater": "Mary Anderson",
			"movie": "Darling Daughter",
			"city": "Louisville",
			"conf": "high",
			"week": "this week",
			"gross": 3500
		},
		{
			"theater": "Mary Anderson",
			"movie": "Darling Daughter",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 5500
		},
		{
			"theater": "Ohio",
			"movie": "Texans",
			"city": "Louisville",
			"conf": "high",
			"week": "this week",
			"gross": 1200
		},
		{
			"theater": "Ohio",
			"movie": "Lady Fights Back",
			"city": "Louisville",
			"conf": "high",
			"week": "this week",
			"gross": 1200
		},
		{
			"theater": "Ohio",
			"movie": "Chan at Monte Carlo",
			"city": "Louisville",
			"conf": "high",
			"week": "this week",
			"gross": 1200
		},
		{
			"theater": "Ohio",
			"movie": "White Banners",
			"city": "Louisville",
			"conf": "high",
			"week": "this week",
			"gross": 1200
		},
		{
			"theater": "Ohio",
			"movie": "Arkansas Traveler",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 1400
		},
		{
			"theater": "Ohio",
			"movie": "Mysterious Rider",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 1400
		},
		{
			"theater": "Ohio",
			"movie": "Professor Beware",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 1400
		},
		{
			"theater": "Ohio",
			"movie": "Gold Diggers in Paris",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 1400
		},
		{
			"theater": "Rialto",
			"movie": "Wife, Husband",
			"city": "Louisville",
			"conf": "high",
			"week": "this week",
			"gross": 6000
		},
		{
			"theater": "Rialto",
			"movie": "Inside Story",
			"city": "Louisville",
			"conf": "high",
			"week": "this week",
			"gross": 6000
		},
		{
			"theater": "Rialto",
			"movie": "Cafe Society",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 5800
		},
		{
			"theater": "Rialto",
			"movie": "Persons in Hiding",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 5800
		},
		{
			"theater": "Strand",
			"movie": "Third of Nation",
			"city": "Louisville",
			"conf": "high",
			"week": "this week",
			"gross": 3200
		},
		{
			"theater": "Strand",
			"movie": "Boy Trouble",
			"city": "Louisville",
			"conf": "high",
			"week": "this week",
			"gross": 3200
		},
		{
			"theater": "Strand",
			"movie": "Moto's Last Warning",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 3500
		},
		{
			"theater": "Strand",
			"movie": "Three Musketeers",
			"city": "Louisville",
			"conf": "high",
			"week": "last week",
			"gross": 3500
		},
		{
			"theater": "Aster",
			"movie": "Spy Hunt",
			"city": "Minneapolis",
			"conf": "high",
			"week": "this week",
			"gross": 1700
		},
		{
			"theater": "Aster",
			"movie": "Smiling Along",
			"city": "Minneapolis",
			"conf": "high",
			"week": "this week",
			"gross": 1700
		},
		{
			"theater": "Aster",
			"movie": "Boy Slaves",
			"city": "Minneapolis",
			"conf": "high",
			"week": "this week",
			"gross": 1700
		},
		{
			"theater": "Aster",
			"movie": "Pardon Nerve",
			"city": "Minneapolis",
			"conf": "high",
			"week": "this week",
			"gross": 1700
		},
		{
			"theater": "Aster",
			"movie": "Chan in Honolulu",
			"city": "Minneapolis",
			"conf": "high",
			"week": "last week",
			"gross": 1800
		},
		{
			"theater": "Aster",
			"movie": "Pirate Skies",
			"city": "Minneapolis",
			"conf": "high",
			"week": "last week",
			"gross": 1800
		},
		{
			"theater": "Century",
			"movie": "Pygmalion",
			"city": "Minneapolis",
			"conf": "high",
			"week": "this week",
			"gross": 5000
		},
		{
			"theater": "Century",
			"movie": "Pygmalion",
			"city": "Minneapolis",
			"conf": "high",
			"week": "last week",
			"gross": 8900
		},
		{
			"theater": "Gopher",
			"movie": "Blondie",
			"city": "Minneapolis",
			"conf": "high",
			"week": "this week",
			"gross": 4000
		},
		{
			"theater": "Gopher",
			"movie": "Great Man",
			"city": "Minneapolis",
			"conf": "high",
			"week": "last week",
			"gross": 900
		},
		{
			"theater": "Orpheum",
			"movie": "Made Me Criminal",
			"city": "Minneapolis",
			"conf": "high",
			"week": "this week",
			"gross": 15000
		},
		{
			"theater": "Orpheum",
			"movie": "Tail Spin",
			"city": "Minneapolis",
			"conf": "high",
			"week": "last week",
			"gross": 4500
		},
		{
			"theater": "State",
			"movie": "Ice Follies",
			"city": "Minneapolis",
			"conf": "high",
			"week": "this week",
			"gross": 6000
		},
		{
			"theater": "State",
			"movie": "Each Other",
			"city": "Minneapolis",
			"conf": "high",
			"week": "last week",
			"gross": 5500
		},
		{
			"theater": "Time",
			"movie": "Assassin Youth",
			"city": "Minneapolis",
			"conf": "high",
			"week": "this week",
			"gross": 2000
		},
		{
			"theater": "Time",
			"movie": "",
			"city": "Minneapolis",
			"conf": "high",
			"week": "last week",
			"gross": 5500
		},
		{
			"theater": "Uptown",
			"movie": "Idiot",
			"city": "Minneapolis",
			"conf": "high",
			"week": "this week",
			"gross": 2800
		},
		{
			"theater": "Uptown",
			"movie": "Stand Up",
			"city": "Minneapolis",
			"conf": "high",
			"week": "last week",
			"gross": 2400
		},
		{
			"theater": "World",
			"movie": "Man Remember",
			"city": "Minneapolis",
			"conf": "high",
			"week": "this week",
			"gross": 1200
		},
		{
			"theater": "World",
			"movie": "Man Remember",
			"city": "Minneapolis",
			"conf": "high",
			"week": "last week",
			"gross": 1400
		},
		{
			"theater": "Criterion",
			"movie": "Honolulu",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "this week",
			"gross": 6000
		},
		{
			"theater": "Criterion",
			"movie": "Oklahoma Kid",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "last week",
			"gross": 7500
		},
		{
			"theater": "Liberty",
			"movie": "Arizona Legion",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "this week",
			"gross": 2900
		},
		{
			"theater": "Liberty",
			"movie": "Great Man",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "this week",
			"gross": 2900
		},
		{
			"theater": "Liberty",
			"movie": "O'Connor",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "last week",
			"gross": 2700
		},
		{
			"theater": "Liberty",
			"movie": "Disbarred",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "last week",
			"gross": 2700
		},
		{
			"theater": "Liberty",
			"movie": "Marry",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "last week",
			"gross": 2700
		},
		{
			"theater": "Liberty",
			"movie": "Society Smuggler",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "last week",
			"gross": 2700
		},
		{
			"theater": "Midwest",
			"movie": "Pygmalion",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "this week",
			"gross": 5500
		},
		{
			"theater": "Midwest",
			"movie": "Paris Honeymoon",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "last week",
			"gross": 4200
		},
		{
			"theater": "Plaza",
			"movie": "Honest Man",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "this week",
			"gross": 1900
		},
		{
			"theater": "Plaza",
			"movie": "Huck Finn",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "last week",
			"gross": 1700
		},
		{
			"theater": "State",
			"movie": "Let Us Live",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "this week",
			"gross": 2700
		},
		{
			"theater": "State",
			"movie": "Stagecoach",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "last week",
			"gross": 3000
		},
		{
			"theater": "Tower",
			"movie": "Oklahoma Kid",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "this week",
			"gross": 2700
		},
		{
			"theater": "Tower",
			"movie": "Musketeers",
			"city": "Oklahoma City",
			"conf": "high",
			"week": "last week",
			"gross": 2100
		},
		{
			"theater": "Albee",
			"movie": "Honest Man",
			"city": "Providence",
			"conf": "high",
			"week": "this week",
			"gross": 3500
		},
		{
			"theater": "Albee",
			"movie": "Secrets Nurse",
			"city": "Providence",
			"conf": "high",
			"week": "this week",
			"gross": 3500
		},
		{
			"theater": "Albee",
			"movie": "Honest Man",
			"city": "Providence",
			"conf": "high",
			"week": "last week",
			"gross": 6800
		},
		{
			"theater": "Albee",
			"movie": "Secrets Nurse",
			"city": "Providence",
			"conf": "high",
			"week": "last week",
			"gross": 6800
		},
		{
			"theater": "Carlton",
			"movie": "Stagecoach",
			"city": "Providence",
			"conf": "high",
			"week": "this week",
			"gross": 5800
		},
		{
			"theater": "Carlton",
			"movie": "Pride Navy",
			"city": "Providence",
			"conf": "high",
			"week": "this week",
			"gross": 5800
		},
		{
			"theater": "Carlton",
			"movie": "Huck Finn",
			"city": "Providence",
			"conf": "high",
			"week": "last week",
			"gross": 7200
		},
		{
			"theater": "Carlton",
			"movie": "Four Girls",
			"city": "Providence",
			"conf": "high",
			"week": "last week",
			"gross": 7200
		},
		{
			"theater": "Fay's",
			"movie": "Alexander's Band",
			"city": "Providence",
			"conf": "high",
			"week": "this week",
			"gross": 5000
		},
		{
			"theater": "Fay's",
			"movie": "Gambling Ship",
			"city": "Providence",
			"conf": "high",
			"week": "last week",
			"gross": 6000
		},
		{
			"theater": "Majestic",
			"movie": "Oklahoma Kid",
			"city": "Providence",
			"conf": "high",
			"week": "this week",
			"gross": 9000
		},
		{
			"theater": "Majestic",
			"movie": "Secret Service",
			"city": "Providence",
			"conf": "high",
			"week": "this week",
			"gross": 9000
		},
		{
			"theater": "Majestic",
			"movie": "Wings Navy",
			"city": "Providence",
			"conf": "high",
			"week": "last week",
			"gross": 5000
		},
		{
			"theater": "Majestic",
			"movie": "Nancy Drew",
			"city": "Providence",
			"conf": "high",
			"week": "last week",
			"gross": 5000
		},
		{
			"theater": "Slate",
			"movie": "Stagecoach",
			"city": "Providence",
			"conf": "high",
			"week": "last week",
			"gross": 14500
		},
		{
			"theater": "Slate",
			"movie": "Pride Navy",
			"city": "Providence",
			"conf": "high",
			"week": "last week",
			"gross": 14500
		},
		{
			"theater": "State",
			"movie": "Ice Follies",
			"city": "Providence",
			"conf": "high",
			"week": "this week",
			"gross": 12500
		},
		{
			"theater": "State",
			"movie": "North China",
			"city": "Providence",
			"conf": "high",
			"week": "this week",
			"gross": 12500
		},
		{
			"theater": "Strand",
			"movie": "Cafe Society",
			"city": "Providence",
			"conf": "high",
			"week": "this week",
			"gross": 8000
		},
		{
			"theater": "Strand",
			"movie": "My Son",
			"city": "Providence",
			"conf": "high",
			"week": "this week",
			"gross": 8000
		},
		{
			"theater": "Strand",
			"movie": "Beachcomber",
			"city": "Providence",
			"conf": "high",
			"week": "last week",
			"gross": 8500
		},
		{
			"theater": "Strand",
			"movie": "Miss X",
			"city": "Providence",
			"conf": "high",
			"week": "last week",
			"gross": 8500
		},
		{
			"theater": "Fox",
			"movie": "Wife, Husband",
			"city": "San Francisco",
			"conf": "high",
			"week": "this week",
			"gross": 16500
		},
		{
			"theater": "Fox",
			"movie": "Persons Hiding",
			"city": "San Francisco",
			"conf": "high",
			"week": "this week",
			"gross": 16500
		},
		{
			"theater": "Fox",
			"movie": "Freedom Ring",
			"city": "San Francisco",
			"conf": "high",
			"week": "last week",
			"gross": 13000
		},
		{
			"theater": "Fox",
			"movie": "Four Girls",
			"city": "San Francisco",
			"conf": "high",
			"week": "last week",
			"gross": 13000
		},
		{
			"theater": "Golden Gate",
			"movie": "Flying Irishman",
			"city": "San Francisco",
			"conf": "high",
			"week": "this week",
			"gross": 13000
		},
		{
			"theater": "Golden Gate",
			"movie": "Saint San Francisco",
			"city": "San Francisco",
			"conf": "high",
			"week": "last week",
			"gross": 11500
		},
		{
			"theater": "Orpheum",
			"movie": "Honest Man",
			"city": "San Francisco",
			"conf": "high",
			"week": "this week",
			"gross": 6500
		},
		{
			"theater": "Orpheum",
			"movie": "Son Criminal",
			"city": "San Francisco",
			"conf": "high",
			"week": "this week",
			"gross": 6500
		},
		{
			"theater": "Orpheum",
			"movie": "Honest Man",
			"city": "San Francisco",
			"conf": "high",
			"week": "last week",
			"gross": 8500
		},
		{
			"theater": "Orpheum",
			"movie": "Son Criminal",
			"city": "San Francisco",
			"conf": "high",
			"week": "last week",
			"gross": 8500
		},
		{
			"theater": "Paramount",
			"movie": "Freedom Ring",
			"city": "San Francisco",
			"conf": "high",
			"week": "this week",
			"gross": 8300
		},
		{
			"theater": "Paramount",
			"movie": "Four Girls",
			"city": "San Francisco",
			"conf": "high",
			"week": "this week",
			"gross": 8300
		},
		{
			"theater": "Paramount",
			"movie": "Wings Navy",
			"city": "San Francisco",
			"conf": "high",
			"week": "last week",
			"gross": 8500
		},
		{
			"theater": "Paramount",
			"movie": "Arizona Wildcat",
			"city": "San Francisco",
			"conf": "high",
			"week": "last week",
			"gross": 8500
		},
		{
			"theater": "St. Francis",
			"movie": "Pygmalion",
			"city": "San Francisco",
			"conf": "high",
			"week": "this week",
			"gross": 6000
		},
		{
			"theater": "St. Francis",
			"movie": "Pygmalion",
			"city": "San Francisco",
			"conf": "high",
			"week": "last week",
			"gross": 6000
		},
		{
			"theater": "United Artists",
			"movie": "Each Other",
			"city": "San Francisco",
			"conf": "high",
			"week": "this week",
			"gross": 11000
		},
		{
			"theater": "United Artists",
			"movie": "Topper",
			"city": "San Francisco",
			"conf": "high",
			"week": "last week",
			"gross": 5700
		},
		{
			"theater": "Warfield",
			"movie": "Ice Follies",
			"city": "San Francisco",
			"conf": "high",
			"week": "this week",
			"gross": 13500
		},
		{
			"theater": "Warfield",
			"movie": "Secret Service",
			"city": "San Francisco",
			"conf": "high",
			"week": "this week",
			"gross": 13500
		},
		{
			"theater": "Warfield",
			"movie": "Darling Daughter",
			"city": "San Francisco",
			"conf": "high",
			"week": "last week",
			"gross": 8000
		},
		{
			"theater": "Warfield",
			"movie": "Pardon Nerve",
			"city": "San Francisco",
			"conf": "high",
			"week": "last week",
			"gross": 8000
		},
		{
			"theater": "Blue Mouse",
			"movie": "Stagecoach",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 2900
		},
		{
			"theater": "Blue Mouse",
			"movie": "Bulldog Drummond",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 2900
		},
		{
			"theater": "Blue Mouse",
			"movie": "Gunga Din",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 2700
		},
		{
			"theater": "Coliseum",
			"movie": "Kentucky",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 2500
		},
		{
			"theater": "Coliseum",
			"movie": "Goes My Heart",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 2500
		},
		{
			"theater": "Coliseum",
			"movie": "Sweethearts",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 2300
		},
		{
			"theater": "Coliseum",
			"movie": "Thanks Memory",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 2300
		},
		{
			"theater": "Fifth Avenue",
			"movie": "Freedom Ring",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 6000
		},
		{
			"theater": "Fifth Avenue",
			"movie": "Four Girls",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 6000
		},
		{
			"theater": "Fifth Avenue",
			"movie": "Beachcomber",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 7200
		},
		{
			"theater": "Fifth Avenue",
			"movie": "Boy Trouble",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 7200
		},
		{
			"theater": "Liberty",
			"movie": "Blondie",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 3500
		},
		{
			"theater": "Liberty",
			"movie": "North of Shanghan",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 3500
		},
		{
			"theater": "Liberty",
			"movie": "Let Live",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 3800
		},
		{
			"theater": "Liberty",
			"movie": "Spy Hunt",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 3800
		},
		{
			"theater": "Music Box",
			"movie": "Pygmalion",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 4500
		},
		{
			"theater": "Music Box",
			"movie": "Pygmalion",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 5200
		},
		{
			"theater": "Orpheum",
			"movie": "Honest Man",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 6500
		},
		{
			"theater": "Orpheum",
			"movie": "Wharf",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 6500
		},
		{
			"theater": "Orpheum",
			"movie": "Three Musketeers",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 4100
		},
		{
			"theater": "Orpheum",
			"movie": "Chan in Honolulu",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 4100
		},
		{
			"theater": "Palomar",
			"movie": "Man Remember",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 3600
		},
		{
			"theater": "Palomar",
			"movie": "Thoroughbreds",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 3600
		},
		{
			"theater": "Palomar",
			"movie": "Woman Doctor",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 4500
		},
		{
			"theater": "Palomar",
			"movie": "Tom Sawyer",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 4500
		},
		{
			"theater": "Paramount",
			"movie": "Cafe Society",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 5500
		},
		{
			"theater": "Paramount",
			"movie": "Persons Hiding",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 5500
		},
		{
			"theater": "Paramount",
			"movie": "Stagecoach",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 7700
		},
		{
			"theater": "Paramount",
			"movie": "Bulldog Drummond",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 7700
		},
		{
			"theater": "Roosevelt",
			"movie": "Dawn Patrol",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 2100
		},
		{
			"theater": "Roosevelt",
			"movie": "Heart of North",
			"city": "Seattle",
			"conf": "high",
			"week": "this week",
			"gross": 2100
		},
		{
			"theater": "Roosevelt",
			"movie": "Angels",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 2500
		},
		{
			"theater": "Roosevelt",
			"movie": "Woman Again",
			"city": "Seattle",
			"conf": "high",
			"week": "last week",
			"gross": 2500
		}
	]
}



"""

prompt4="""

Now here is the image for you to extract tuples from:

Input image:

"""

system_instruction = """You are a helpful assistant performing OCR into a structured format.  The output should be valid json"""  


def proc(image_filename, thinking_level, force_thinking_budget):


	resolution=None

	# fall back to gemini-2.5 if gemini 3 goes over thinking budget at both "high" and "low" levels

	if force_thinking_budget:

		with open(shotFile1, 'rb') as f:
			image_bytes = f.read()

			shot_data1 = types.Part.from_bytes(
				data=image_bytes,
				mime_type='image/jpeg',
			)


		with open(shotFile2, 'rb') as f:
			image_bytes = f.read()

			shot_data2 = types.Part.from_bytes(
				data=image_bytes,
				mime_type='image/jpeg',
			)


		with open(image_filename, 'rb') as f:
			image_bytes = f.read()

			image_data = types.Part.from_bytes(
				data=image_bytes,
				mime_type='image/jpeg',
			)


		response = client.models.generate_content(
				model="gemini-2.5-pro",
				contents=[
					prompt1, 
					shot_data1,
					prompt2,
					shot_data2,
					prompt3,
					prompt4,
					image_data,
					"\nOutput json:"
					

				],
				config=GenerateContentConfig(
					system_instruction=system_instruction,
					response_mime_type="application/json",
					response_json_schema=OutputFormat.model_json_schema(),
					thinking_config=types.ThinkingConfig(thinkingBudget=1000),
					media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH
				)
			)  

		resolution="MEDIA_RESOLUTION_HIGH"

	else:

		with open(shotFile1, 'rb') as f:
			image_bytes = f.read()

			shot_data1 = types.Part.from_bytes(
				data=image_bytes,
				mime_type='image/jpeg',

				media_resolution=types.PartMediaResolution(
					level=types.PartMediaResolutionLevel.MEDIA_RESOLUTION_ULTRA_HIGH # High resolution
				),
			)


		with open(shotFile2, 'rb') as f:
			image_bytes = f.read()

			shot_data2 = types.Part.from_bytes(
				data=image_bytes,
				mime_type='image/jpeg',
				media_resolution=types.PartMediaResolution(
					level=types.PartMediaResolutionLevel.MEDIA_RESOLUTION_ULTRA_HIGH # High resolution
				),
			)


		with open(image_filename, 'rb') as f:
			image_bytes = f.read()

			image_data = types.Part.from_bytes(
				data=image_bytes,
				mime_type='image/jpeg',
				media_resolution=types.PartMediaResolution(
					level=types.PartMediaResolutionLevel.MEDIA_RESOLUTION_ULTRA_HIGH # High resolution

				),
			)

		resolution="MEDIA_RESOLUTION_ULTRA_HIGH"

		response = client.models.generate_content(
			model=MODEL_ID,
			contents=[
				prompt1, 
				shot_data1,
				prompt2,
				shot_data2,
				prompt3,
				prompt4,
				image_data,
				"\nOutput json:"
				

			],
			config=GenerateContentConfig(
				system_instruction=system_instruction,
				response_mime_type="application/json",
				response_json_schema=OutputFormat.model_json_schema(),
				thinking_config=types.ThinkingConfig(thinking_level=thinking_level)
			)
		)       

	response_dict = response.model_dump(mode='json')
	return response_dict, resolution


def proc_one(inputFile, output, thinking_level, force_thinking_budget):
	response, resolution=proc(inputFile, thinking_level, force_thinking_budget)

	if len(response) > 0:
		with open(output, "w") as out:
			
			response["thinking_level"]=thinking_level
			response["force_thinking_budget"]=force_thinking_budget
			response["resolution"]=str(resolution)

			json.dump(response, out, indent=4)





def proc_all(folder):

	for input_path in glob.glob("%s/*.jpg" % (folder)):
	
		idd=input_path.split("/")[-1]

		sys.stdout.flush()
		idd=re.sub(r"\.pdf$", ".jsonl", idd)
		idd=re.sub(r"\.jpg$", ".jsonl", idd)
		output_path="%s/%s" % (outdir, idd)
		
		redo=False
		
		thinking_level="high"
		force_thinking_budget=False

		# order:
		# gemini 3, thinking level=high
		# else gemini 3, thinking level=low
		# else gemini 2.5 pro, thinking budget=30000
		
		if os.path.exists(output_path):
			with open(output_path) as out2:
				data=json.load(out2)
				if "candidates" in data:
					cand=data["candidates"][0]
					if "finish_reason" in cand:
						finish_reason=cand["finish_reason"]
						if finish_reason == "MAX_TOKENS":

							old_thinking_level=data["thinking_level"]
							old_force_thinking_budget=data["force_thinking_budget"]

							if old_thinking_level == "high":

								redo=True
								thinking_level="low"

							elif old_thinking_level == "low" and old_force_thinking_budget is False:
								
								redo=True
								thinking_level="low"
								force_thinking_budget=True

							else:

								redo=True
								thinking_level="low"
								force_thinking_budget=True


		try:
			if redo or not os.path.exists(output_path):
				proc_one(input_path, output_path, thinking_level, force_thinking_budget)
				
		except genai.errors.ServerError as e:
			print(e)
			time.sleep(60)
		except Exception as e:
			print(e)


proc_all(INPUT_DIR)


