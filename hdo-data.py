#!/usr/bin/python3

## HDO data extractor for PRE-Distribuce
#
# Inputs:
#   HDO code
#   number of days ahead
#
# Output: Records in format: START_DATE END_DATE LETTER,
# where START_DATE and END_DATE are ISO formatted strings, and LETTER is 'N' or 'V'
#

from bs4 import BeautifulSoup
import requests
import re
from datetime import datetime, timedelta, timezone

def dateIterator(start: datetime, notAfter: datetime, step: timedelta):
    i = start
    while i < notAfter:
        yield i
        i = i + step

def firstMatching(collection, matcher, noMatches = None):
    for matcherResult in map(matcher, collection):
        if matcherResult is not None:
            return matcherResult
    return noMatches

class DstPeriod:

    storeDateFormat = "%Y-%m-%d %H:%M:%S %z"

    recordsByCountry = {
        "CZ": [
             { "from": "2023-03-26 01:00:00 +0000", "until": "2023-10-29 00:59:59 +0000", "gmtOffsetSeconds": 7200 }
            ,{ "from": "2023-10-29 01:00:00 +0000", "until": "2024-03-31 00:59:59 +0000", "gmtOffsetSeconds": 3600 }
            ,{ "from": "2024-03-31 01:00:00 +0000", "until": "2024-10-27 00:59:59 +0000", "gmtOffsetSeconds": 7200 }
            ,{ "from": "2024-10-27 01:00:00 +0000", "until": "2025-03-30 00:59:59 +0000", "gmtOffsetSeconds": 3600 }
            ,{ "from": "2025-03-30 01:00:00 +0000", "until": "2025-10-26 00:59:59 +0000", "gmtOffsetSeconds": 7200 }
            ,{ "from": "2025-10-26 01:00:00 +0000", "until": "2026-03-29 00:59:59 +0000", "gmtOffsetSeconds": 3600 }
            ,{ "from": "2026-03-29 01:00:00 +0000", "until": "2026-10-25 00:59:59 +0000", "gmtOffsetSeconds": 7200 }
            #,{ "from": "", "until": "", "gmtOffsetSeconds": }
        ]
    }

    # Get DST period by time and country
    # a.k.a. "At this time, what was GMT offset in this country?"
    @classmethod
    def byTimeAndPlace(_, pointInTime: datetime, place: str):
        if not place in DstPeriod.recordsByCountry:
            raise ValueError("Unknown location %s" % place)

        foundPeriod = firstMatching(
            map(lambda storedPeriod: DstPeriod(storedPeriod), DstPeriod.recordsByCountry[place]),
            lambda dstPeriod, pointInTime=pointInTime: dstPeriod if pointInTime >= dstPeriod.from_ and pointInTime <= dstPeriod.until else None,
            None # If not found
        )

        if foundPeriod is None:
            raise ValueError("DST period not defined for time %s in %s" % (pointInTime, place))

        return foundPeriod

    def __init__(self, storedObject: dict):
        self.from_ = datetime.strptime(storedObject["from"], DstPeriod.storeDateFormat)
        self.until = datetime.strptime(storedObject["until"], DstPeriod.storeDateFormat)
        self.timezone = timezone(timedelta(seconds=storedObject["gmtOffsetSeconds"]))


        foundRecord = firstMatching

# When one would be in a country at a specified time, and have seen a local timestamp, what universal time would that timestamp specify?
def timestampAsSeenAtAndIn(string: str, format: str, seenAt: datetime, seenIn: str) -> datetime:

    parsedDate = datetime.strptime(string, format)
    parsedDate = parsedDate.replace(tzinfo = DstPeriod.byTimeAndPlace(seenAt, seenIn).timezone)

    return parsedDate


def log(level = 'INFO', message = ""):
    print("[%s] %s" % (level, message))
# /log

def getTariffTableForNext (hdoCommand: int, days: int):

    # Prepare dates
    requestStartDate = datetime.now().astimezone() # = Date in local timezone. Needed to have expected day number.
    currentDstPeriod = DstPeriod.byTimeAndPlace(requestStartDate, 'CZ')

    # Request data only until this date
    # To keep things simple:
    # - do not go over last day of the year
    # - do not go over last day of current DST period
    requestEndDate = min(
        currentDstPeriod.until - timedelta(days = 1),
        requestStartDate.replace(month=12, day=31),
        requestStartDate + timedelta(days = days - 1)
    )

    # Prepare URL
    urlTemplate = "https://www.predistribuce.cz/cs/potrebuji-zaridit/zakaznici/stav-hdo/?povel=%d&den_od=%02d&mesic_od=%02d&rok_od=%d&den_do=%02d&mesic_do=%02d&rok_do=%d"
    url = urlTemplate % ( hdoCommand, requestStartDate.day, requestStartDate.month, requestStartDate.year, requestEndDate.day, requestEndDate.month, requestEndDate.year )
    print("url = %s" % url)

    # Request HTML page
    response = requests.get(url)

    # Parse response
    soup = BeautifulSoup(response.text, 'html.parser');

    # Process the bars
    for barElement in soup.find(id="component-hdo-vice-dni-url").find_all(class_='hdo-bar'):
        barCompoundDatesString = barElement.find(class_="blue-text").text.strip() # 03.04. -  07.04. or 08.04.
        matches = re.search("^([0-9.]+) +[-] +([0-9.]+)$", barCompoundDatesString)
        if matches:
            # Bar for date interval
            barStartDateString = matches.group(1)
            barEndDateString = matches.group(2)
        else:
            # Bar for single date
            barStartDateString = barCompoundDatesString
            barEndDateString = barCompoundDatesString

        barStartDateObject = timestampAsSeenAtAndIn("%s%d 01:01:00" % (barStartDateString, requestStartDate.year), '%d.%m.%Y %H:%M:%S', requestStartDate, 'CZ')
        barEndDateObject = timestampAsSeenAtAndIn("%s%d 01:01:01" % (barEndDateString, requestStartDate.year), '%d.%m.%Y %H:%M:%S', requestStartDate, 'CZ')

        for barIteratorDate in dateIterator(barStartDateObject, barEndDateObject, timedelta(hours = 24)):

            currentTariff = None
            for element in barElement.select('.hdovt, .hdont, .span-overflow'):
                if element['class'][0] == 'hdovt':
                    currentTariff = 'V'
                elif element['class'][0] == 'hdont':
                    currentTariff = 'N'
                else:
                    matches = re.search('^([0-9]{2}):([0-9]{2}) - (([0-9]{2}):([0-9]{2}))$', element['title'])
                    if matches.group(3) == "00:00":
                        endDate = barIteratorDate.replace(hour=0, minute=0) + timedelta(hours=24)
                    else:
                        endDate = barIteratorDate.replace(hour=int(matches.group(4)), minute=int(matches.group(5)))

                    yield {
                        "start": barIteratorDate.replace(hour=int(matches.group(1)), minute=int(matches.group(2))),
                        "end": endDate - timedelta(seconds=1),
                        "tariff": currentTariff
                    }


for record in getTariffTableForNext(hdoCommand=568, days=14):
    print("%s %s %s" % (record["start"].isoformat(), record["end"].isoformat(), record["tariff"]))



