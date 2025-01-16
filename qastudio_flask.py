from flask import Flask, request, jsonify
from openai import OpenAI
import os
from dotenv import load_dotenv
import time
import json

# 환경 변수 로드
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Flask 애플리케이션 생성
app = Flask(__name__)

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=OPENAI_API_KEY)

# assistant function 더미 정의 영역

# 프로젝트 분석 함수
project_function = {
    "type": "function",
    "function": {
        "name": "generate_project_info",
        "description": "Learn the registered project .zip file and return the full page information that exists when this project file is deployed as the actual url",
        "strict": True,
        "parameters": {
            "type": "object",
            "required": [
            "project",
            "pages"
            ],
            "properties": {
            "project": {
                "type": "object",
                "required": [
                "description",
                "view_type",
                "development_skill"
                ],
                "properties": {
                "description": {
                    "type": "string",
                    "description": "Description of the project"
                },
                "view_type": {
                    "type": "string",
                    "description": "view_type (pc or mobile)"
                },
                "development_skill": {
                    "type": "string",
                    "description": "development_skill (next or react or vanilla)"
                }
                },
                "additionalProperties": False
            },
            "pages": {
                "type": "array",
                "description": "List of Project Pages",
                "items": {
                "type": "object",
                "required": [
                    "name",
                    "path",
                    "description",
                    "senario"
                ],
                "properties": {
                    "name": {
                    "type": "string",
                    "description": "Name of the page"
                    },
                    "path": {
                    "type": "string",
                    "description": "Path of the page"
                    },
                    "description": {
                    "type": "string",
                    "description": "Description of the page"
                    },
                    "senario": {
                    "type": "object",
                    "required": [
                        "steps"
                    ],
                    "properties": {
                        "steps": {
                        "type": "array",
                        "description": "List of Scenario Steps",
                        "items": {
                            "type": "string",
                            "description": "Description of each step"
                        }
                        }
                    },
                    "additionalProperties": False
                    }
                },
                "additionalProperties": False
                }
            }
            },
            "additionalProperties": False
        }
    }
}

# 시나리오 생성 함수
senario_function = {
    "type": "function",
    "function": {
        "name": "define_user_scenarios",
        "description": "Define user scenarios for a project based on the target user's actions in a service.",
        "strict": True,
        "parameters": {
            "type": "object",
            "required": [
            "title",
            "description",
            "scenarios"
            ],
            "properties": {
            "title": {
                "type": "string",
                "description": "The title of the project"
            },
            "description": {
                "type": "string",
                "description": "A description of the project"
            },
            "scenarios": {
                "type": "array",
                "description": "List of scenarios that define the user actions",
                "items": {
                "type": "object",
                "required": [
                    "step",
                    "description",
                    "elements"
                ],
                "properties": {
                    "step": {
                    "type": "integer",
                    "description": "The order step of the scenario"
                    },
                    "description": {
                    "type": "string",
                    "description": "Description of the scenario step"
                    },
                    "elements": {
                    "type": "array",
                    "description": "Elements involved in the scenario step",
                    "items": {
                        "type": "object",
                        "required": [
                        "name",
                        "type",
                        "locator",
                        "action"
                        ],
                        "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the UI element"
                        },
                        "type": {
                            "type": "string",
                            "description": "The type of the UI element (e.g., button, input)"
                        },
                        "locator": {
                            "type": "object",
                            "required": [
                            "strategy",
                            "value"
                            ],
                            "properties": {
                            "strategy": {
                                "type": "string",
                                "description": "The locator strategy (e.g., id, class name)"
                            },
                            "value": {
                                "type": "string",
                                "description": "The locator value to find the element"
                            }
                            },
                            "additionalProperties": False
                        },
                        "action": {
                            "type": "object",
                            "required": [
                            "type",
                            "value"
                            ],
                            "properties": {
                            "type": {
                                "type": "string",
                                "description": "The type of action (e.g., click, type)"
                            },
                            "value": {
                                "type": "string",
                                "description": "The value associated with the action (e.g., text to input)"
                            }
                            },
                            "additionalProperties": False
                        }
                        },
                        "additionalProperties": False
                    }
                    }
                },
                "additionalProperties": False
                }
            }
            },
            "additionalProperties": False
        }
    }
}

##################################################

# 사용자 정의 함수 영역

# 새로운 스레드를 생성하는 함수
def create_new_thread():
    thread = client.beta.threads.create()
    return thread

# 반복문에서 대기하는 함수
def wait_on_run(run, thread_id):
    while run.status == "queued" or run.status == "in_progress":
        # 3-3. 실행 상태를 최신 정보로 업데이트합니다.
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id,
        )
        time.sleep(0.5)
    return run


# 스레드에 종속된 메시지를 추가하는 함수
def submit_message(assistant_id, thread_id, function_name, user_message):
    # print("steo 0...")
    client.beta.threads.messages.create(
        thread_id=thread_id, role="user", content=user_message
    )

    # print("steo 1...")
    """특정 함수를 호출하는 메시지를 생성하고 실행."""

    # print("steo 2...")
    # 메시지 추가 및 실행

    if function_name == "generate_project_info":
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=assistant_id,
            tools=[
                project_function,  # 프로젝트 분석 함수 정의
            ],
        )
        # print("step 3...")
        return run.required_action.submit_tool_outputs.tool_calls[0].function.arguments

    elif function_name == "define_user_scenarios":
        # 시나리오 작성 함수
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=assistant_id,
            tools=[
                senario_function,  # 시나리오 작성 함수 정의
            ],
        )
        # print("step 3...")
        return run.required_action.submit_tool_outputs.tool_calls[0].function.arguments

    else:  # 다른 경우 처리
        return jsonify({
            "success": False,
            "msg": f"Unknown function: {function_name}",
            "error": str(e)
        }), 500

# 스레드에 종속된 메시지를 조회하는 함수
def get_response(thread_id):
    # print(client.beta.threads.messages.list(thread_id=thread_id, order="asc"))
    return client.beta.threads.messages.list(thread_id=thread_id, order="asc")

def ask(assistant_id, thread_id, function_name, user_message):
    # print("message sumiting...")
    response = submit_message(
        assistant_id,
        thread_id,
        function_name,
        user_message,
    )
    # print("submitted")
    return response

def show_json(obj):
    # obj의 모델을 JSON 형태로 변환한 후 출력합니다.
    print(json.loads(obj.model_dump_json()))


def upload_file(user_id, project_id, filename):
    try:
        # 파일 업로드
        # print("Uploading file....")
        file = client.files.create(
        file=open('./project_files/' + f"user{user_id}s{project_id}th{filename}.zip", "rb"),
            purpose='assistants'
        )
    except Exception as e:
        return jsonify({
            "success": False,
            "msg": "실패",
            "error": str(e)
        }), 500
    
    # print("Creating assistant...")
    assistant = client.beta.assistants.create(
            name=f"{user_id}'s assistant {project_id}", # 이름은 플젝 id로 생성하기
            instructions=(
                # AI 1차 학습용 텍스트
                "You are a tool to help QA by analyzing projects and writing multiple user-specific scenarios."
            ),
            model="gpt-4o",
            tools=[
                {"type": "code_interpreter"}, # zip 파일이라 code interpreter만 가능
            ],
            tool_resources={
                "code_interpreter": {
                    "file_ids": [file.id], # zip file 학습용
                }
            }
        )
    # show_json(assistant)
    # print("Assistant created successfully.")
    
    return assistant.id
        
##################################################

# flask api 정의 영역
"""
curl -X POST http://127.0.0.1:5000/api/v1/ai/project/information \
    -F "user_id=1" \
    -F "project_id=1" \
    -F "file=@./project/namamap-web.zip"
"""
@app.route('/api/v1/ai/project/information', methods=['POST'])
def ask_project_information():
    """프로젝트 분석 질문 API."""
    file = request.files['file']
    user_id = request.form['user_id']
    project_id = request.form['project_id']

    # 저장 경로 설정
    file_path = './project_files/' + f"user{user_id}s{project_id}th{file.filename}.zip"

    # 기존 파일이 있는 경우 삭제
    if os.path.exists(file_path):
        os.remove(file_path)

    # 파일 저장
    file.save(file_path)

    assistant_id = upload_file(user_id, project_id, file.filename)
    
    thread_id = create_new_thread().id

    question = "Learn the registered project .zip file and return the full page information that exists when the project file is distributed to the actual url (as in ex. \"/login\")" + "The full page information should be about the file I uploaded."

    try:
        # 어시스턴트 생성 및 질문 처리
        # print("asking...")
        response = ask(
            assistant_id,
            thread_id,
            "generate_project_info",
            question
        )

        # print("Asking Successful.")

        return jsonify({
            "success": True,
            "msg": "성공",
            "data": {
                "response": response,
                "assistant_id": assistant_id  # 추가된 assistant_id
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "msg": "실패",
            "error": str(e)
        }), 500
    
"""
curl -X POST http://127.0.0.1:5000/api/v1/ai/project/character/create \
-H "Content-Type: application/json" \
-d '{
    "assistant_id": "asst_rLQy3EfkILzqiJmdFCGvGUaU",
    "name": "일반 유저",
    "description": "로그인을 하려는 일반 유저"
}'
"""
@app.route('/api/v1/ai/project/character/create', methods=['POST'])
def ask_senarios():
    """시나리오 생성 질문 질문 API."""
    assistant_id = request.json['assistant_id']
    name = request.json['name']
    description = request.json['description']
    
    thread_id = create_new_thread().id

    question = f"Scenario the representative action of user {name} with {description} in this project" + "Scenario should be about the file I uploaded" + "Scenario should work perfectly when converted to selenium code."

    try:
        # 어시스턴트 생성 및 질문 처리
        # print("asking...")
        response = ask(
            assistant_id,
            thread_id,
            "define_user_scenarios",
            question
        )

        # print("Asking Successful.")
        # print(response)

        return jsonify({"success": True, "msg": "성공", "data": response})

    except Exception as e:
        return jsonify({
            "success": False,
            "msg": "실패",
            "error": str(e)
        }), 500
    
"""
curl -X POST http://<your-server-domain>/delete \
-H "Content-Type: application/json" \
-d '{"assistant_id": "<your_assistant_id>"}'
"""
@app.route('/delete', methods=['POST'])
def delete_file():
    """assistant 제거 API."""
    data = request.json
    assistant_id = data.get('assistant_id')
    if not assistant_id:
        return jsonify({
            "success": False,
            "msg": "File ID is required",
            "error": str(e)
        }), 400

    try:
        # 파일 제거
        client.beta.assistants.delete(assistant_id)

        return jsonify({
                "success": True,
                "msg": "성공",
                "data": {}
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "msg": "실패",
            "error": str(e)
        }), 500

@app.route('/file', methods=['GET'])
def get_file_id():
    """Files 조회 API."""
    try:
        # 파일 조회
        files = client.files.list()
        serializable_files = [{"id": f.id, "name": f.name} for f in files]  # 직렬화

        return jsonify({
            "success": True,
            "msg": "성공",
            "data": {
                "files": serializable_files
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "msg": "실패",
            "error": str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5050)

##################################################