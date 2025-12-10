#!/usr/bin/env python3
import logging

from youtube_transcript_api import YouTubeTranscriptApi

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_transcript(video_id):
    try:
        # For version 0.6.x and newer, get_transcript is a static method on the class
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        print(f"Success! Got {len(transcript)} lines.")
    except Exception as e:
        print(f"Error: {e}")
        # Fallback check for instance method (unlikely for this lib but checking)
        try:
            api = YouTubeTranscriptApi()
            transcript = api.get_transcript(video_id)
            print(f"Success (instance)! Got {len(transcript)} lines.")
        except Exception as e2:
            print(f"Error (instance): {e2}")


if __name__ == "__main__":
    fetch_transcript("_OqVDO99YVM")
