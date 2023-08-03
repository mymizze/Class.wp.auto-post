import config
import requests, openai
from bs4 import BeautifulSoup
from time import sleep

# 글로벌 변수 선언
CNT_POST = 0

# ChatGPT 컨텐츠 생성 함수
def generateChatGPT(topic, category, numTags, model='text-davinci-003', maxTokens=3900):
    # ChatGPT API 인증
    openai.organization = config.openai_organization
    openai.api_key = config.openai_apiKey

    # 타이틀 생성
    prompt = f"""
        As a very proficient SEO writer, I am writing a blog about {category}.
        Here are 1 potential blog subjects that would fit well with the topic name "{topic}",
        recommend a sentimental title.
    """
    res = openai.Completion.create(model=model, prompt=prompt, max_tokens=maxTokens)
    title = res["choices"][0]["text"]
    title = title.replace('\n','').replace('\"','').replace('-','').strip()
    print('타이틀 생성 완료')

    # 태그 조합
    prompt = f"""
        Generate {str(numTags)} hashtags fit to this blog title, {title} using Korean.
        Don't use "#" in front of each tag, connect each hashtag with comma.
    """
    res = openai.Completion.create(model=model, prompt=prompt, max_tokens=maxTokens)
    tag = res["choices"][0]["text"]
    tag = tag.replace('\n','').replace('\"','').strip()

    # 태그 공백제거 후 리스트 타입
    arrTags = tag.split(',')
    listTags = list()
    for item in arrTags:
        listTags.append(item.strip())

    print('태그 조합 완료')

    # 본문 응답 프롬프트
    try:
        prompt = f"""
            As a very proficient SEO writer, I am writing a blog about {category}.

            Create a blog for "{topic}". Its category is {category}.

            Write a 2000 word blog article except H1 tag in body tag of html format.
            Contains subtitles and detailed descriptions.
        """
        body = openai.Completion.create(model=model, prompt=prompt, max_tokens=maxTokens)
        body = body["choices"][0]["text"]

        # 특정 html H1 태그 행 삭제
        soup = BeautifulSoup(body, 'html.parser')
        for row in soup.select('h1'):
            row.decompose()
        body = str(soup)

        # 불필요 글자 제거
        body = body.replace('#', '')

        # 본문 목차 포함하여 문자열 조합 완성
        contents = f"<!-- wp:luckywp/tableofcontents /-->\n{body}"

        print('본문 생성 완료')
    except Exception as e:
        print(e)
        return ""

    # 반환 값 설정
    response =  {
        'title': title,
        'tag' : listTags,
        'category' : category,
        'contents' : contents
    }

    print('ChatGPT 프로세스 완료')

    return response



# 워드프레스 자동 포스팅 함수
def createPost(postInfo):
    try:
        print('워드프레스 포스팅 중...')

        # 워드프레스 JWT 인증 토큰 얻기
        url = f"https://{config.url}/wp-json/jwt-auth/v1/token"
        data = {
            'username': config.id,
            'password':config.pw
        }
        res = requests.post(url, data=data).json()
        token = res.get('token')

        # 헤더에 JWT 인증 토큰 데이터 추가
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}'
        }

        # 워드프레스 포스팅 데이터 설정
        postURL = f"https://{config.url}/wp-json/wp/v2/posts"
        postData = {
            'title': postInfo.get('title'),
            'slug': postInfo.get('title').replace(' ', '-'),
            'content': postInfo.get('contents'),
            'meta': {
                'category': postInfo.get('category')
            },
            'status': postInfo.get('status')
        }

        # 워드프레스 포스팅 생성 요청 보내기
        response = requests.post(postURL, json=postData, headers=headers)

        # 응답 결과 확인
        if response.status_code == 201:
            # 워드프레스 포스팅 ID
            postedID = response.json().get('id')

            # 태그 설정
            arrTags = list()
            for item in postInfo.get('tags'):
                # 태그 신규 생성 및 태그 Relationships 테이블에 등록할 id 값 구하기
                url = f"https://{config.url}/wp-json/wp/v2/tags"
                params = {
                    'search': item
                }
                res = requests.get(url, params=params).json()

                if len(res) < 1:
                    # 태그 신규 등록 후 id 값 수집
                    tagData = {
                        'name': item
                    }
                    tagsURL = 'https://'+config.url+'/wp-json/wp/v2/tags'
                    resTag = requests.post(tagsURL, json=tagData, headers=headers).json()
                    arrTags.append(resTag.get('id'))
                else:
                    # 이미 등록 된 태그 id 값 수집
                    arrTags.append(res[0].get('id'))

            # 태그를 쉼표 구분자로 이용해 한 문장으로 변경 (ex. 태그1,태그2,태그3)
            strTags = ','.join(map(str, arrTags))

            # 워드프레스 신규 포스팅에 태그 값 업데이트
            updatePostData = {
                'tags': strTags
            }
            postURL = f"https://{config.url}/wp-json/wp/v2/posts/{postedID}"
            response = requests.post(postURL, json=updatePostData, headers=headers).json()

        print('워드프레스 포스팅 완료')

    except Exception as e:
        print(e)
        return ""


"""
    메인 프로세스
"""
if __name__ == "__main__":
    for topic in config.topics:
        # 포스팅 카운트 글로벌 변수 값 증가
        CNT_POST = CNT_POST + 1

        print(f"================= {CNT_POST} 번째 프로세스 시작 =================")

        # ChatGPT 새 글 생성
        response = generateChatGPT(topic, config.category, config.numTags)

        # 워드프레스 포스팅 데이터 설정
        postInfo = {
            'title' : response['title'],
            'contents' : response['contents'],
            'category' : response['category'],
            'tags' : response['tag'],
            'status' : 'draft'
        }

        # 워드프레스 포스팅 등록 요청
        createPost(postInfo)
