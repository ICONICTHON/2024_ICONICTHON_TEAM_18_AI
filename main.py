import requests
from fastapi import FastAPI
from pydantic import BaseModel
import fitz
import os
import json
import re
from openai import OpenAI
from confluent_kafka import Producer, Consumer, KafkaError
from contextlib import asynccontextmanager
import asyncio
from dotenv import load_dotenv
import io

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

env = os.getenv("ENV", "dev")
KAFKA_BROKER_URL = os.getenv(f"KAFKA_BROKER_URL_{env.upper()}")

app = FastAPI()

producer_config = {
    'bootstrap.servers': 'kafka-1:9092, kafka-2:9093, kafka-3:9094'
}
producer = Producer(producer_config)

consumer_config = {
    'bootstrap.servers': 'kafka-1:9092, kafka-2:9093, kafka-3:9094',
    'group.id': "pdf_processor_group",
    'auto.offset.reset': 'earliest'
}
consumer = Consumer(consumer_config)
consumer.subscribe(['api.ai'])


class PdfResponse(BaseModel):
    title: str
    overall_summary: str
    sections: list


def download_pdf(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.content


def extract_text_from_pdf(pdf_content):
    pdf_stream = io.BytesIO(pdf_content)
    doc = fitz.open(stream=pdf_stream, filetype="pdf")
    pages = [page.get_text("text") for page in doc]
    title_page = pages[0] if len(pages) > 0 else "No Title"
    main_text = "\n\n".join(pages[1:])
    return title_page, pages, main_text


def determine_structure_based_on_length(num_pages, total_text_length):
    if num_pages <= 2 or total_text_length < 1000:
        return 1, 1
    elif 3 <= num_pages <= 5 or 1000 <= total_text_length < 3000:
        return 3, 2
    else:
        return 5, 3


def gpt_summarize(text, prompt, max_tokens=30):
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"{prompt}\n\n{text}"}],
        max_tokens=max_tokens,
        temperature=0.5
    )
    result = response.choices[0].message.content.strip()
    result = re.sub(r"^[^:]+:\s*", "", result)
    return result


def parse_pdf_as_roadmap(pdf_content):
    title_page, pages, entire_text = extract_text_from_pdf(pdf_content)
    num_pages = len(pages)
    total_text_length = len(entire_text)

    max_sections, max_subtopics = determine_structure_based_on_length(num_pages, total_text_length)
    title = gpt_summarize(title_page, "Extract the title of this document.", max_tokens=20)
    overall_summary = gpt_summarize(entire_text, "Summarize the main purpose of this document.", max_tokens=50)

    roadmap_sections = []
    for i in range(1, max_sections + 1):
        section_title = gpt_summarize(entire_text, f"Identify a concise title for main topic #{i}.", max_tokens=20)
        if not section_title:
            continue
        section_description = gpt_summarize(entire_text, f"Summarize the topic '{section_title}'.", max_tokens=30)

        subtopics = []
        for j in range(1, max_subtopics + 1):
            subtopic_title = gpt_summarize(entire_text, f"Provide a concise title for subtopic #{j} under '{section_title}'.", max_tokens=20)
            subtopic_detail = gpt_summarize(entire_text, f"Describe '{subtopic_title}'.", max_tokens=30)
            learning_objectives_text = gpt_summarize(entire_text, f"Summarize objectives for '{subtopic_title}'.", max_tokens=100)

            checkpoints = re.split(r'\d+\.\s*', learning_objectives_text)
            checkpoints = [obj.strip() for obj in checkpoints if obj.strip()]

            subtopics.append({
                "title": subtopic_title,
                "detail": subtopic_detail,
                "checkpoints": checkpoints
            })

        roadmap_sections.append({
            "title": section_title,
            "description": section_description,
            "subtopics": subtopics
        })

    return {
        "title": title if title else "Document Title Not Found",
        "overall_summary": overall_summary,
        "sections": roadmap_sections
    }


def process_pdf_event(data):
    print("Processing PDF event with data:", data)
    lecture_id = data['lectureId']
    file_url = data['fileName']  # fileName이 S3 URL로 들어옴

    # PDF를 다운로드하고 처리
    print(f"Downloading PDF from URL: {file_url}")
    pdf_content = download_pdf(file_url)
    roadmap_details = parse_pdf_as_roadmap(pdf_content)

    message_payload = {
        "lecture_id": lecture_id,
        "file_url": file_url,
        "title": roadmap_details["title"],
        "overall_summary": roadmap_details["overall_summary"],
        "sections": roadmap_details["sections"]
    }

    producer.produce("ai.api", key=str(lecture_id), value=json.dumps(message_payload))
    producer.flush()
    print("Kafka message produced successfully.")


async def consume_kafka_messages():
    while True:
        try:
            msg = consumer.poll(1.0)  # 1초 대기
            if msg is None:
                await asyncio.sleep(1)
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    print(f"Kafka error: {msg.error()}")
                continue

            print("Message received from Kafka:", msg.value())
            data = json.loads(msg.value().decode('utf-8'))
            process_pdf_event(data)
        except Exception as e:
            print(f"Error in consuming messages: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        consume_task = asyncio.create_task(consume_kafka_messages())
        yield
    except Exception as e:
        print(f"Error in lifespan: {e}")
    finally:
        print("Stopping Kafka message consumer task.")
        consume_task.cancel()
        await consume_task


app = FastAPI(lifespan=lifespan)
