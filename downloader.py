#!/usr/bin/env python

from __future__ import print_function

import sys
import time
import argparse
import lxml.html
import requests
from lxml.cssselect import CSSSelector
import traceback
import psycopg2 as pg2
import re
import random
import json

YOUTUBE_VIDEO_URL = 'https://www.youtube.com/watch?v={youtube_id}'
YOUTUBE_COMMENTS_AJAX_URL_OLD = 'https://www.youtube.com/comment_ajax'
YOUTUBE_COMMENTS_AJAX_URL_NEW = 'https://www.youtube.com/comment_service_ajax'

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36"
cookies = requests.cookies.create_cookie(domain='.youtube.com', name='PREF', value='gl=US&hl=en')


# cookies = {'domain': '.youtube.com', 'httpOnly': 'False', 'name': 'PREF', 'value': 'gl=US&hl=en', 'path': '/'}


def find_value(html, key, num_chars=2, separator='"'):
    pos_begin = html.find(key) + len(key) + num_chars
    pos_end = html.find(separator, pos_begin)
    return html[pos_begin: pos_end]


def ajax_request(session, url, params=None, data=None, headers=None, retries=5, sleep=20):
    for _ in range(retries):
        response = session.post(url, params=params, data=data, headers=headers)
        if response.status_code == 200:
            return response.json()
        if response.status_code in [403, 413]:
            return {}
        else:
            time.sleep(sleep)


def download_comments(youtube_id, sleep=.1):
    if r'\"isLiveContent\":true' in requests.get(YOUTUBE_VIDEO_URL.format(youtube_id=youtube_id)).text:
        print('Live stream detected! Not all comments may be downloaded.')
        # raise Exception('LiveContent')
        return download_comments_new_api(youtube_id, sleep)
    return download_comments_old_api(youtube_id, sleep)


def download_comments_new_api(youtube_id, sleep=1):
    # Use the new youtube API to download some comments
    session = requests.Session()
    session.headers['User-Agent'] = USER_AGENT
    session.cookies.set_cookie(cookies)

    response = session.get(YOUTUBE_VIDEO_URL.format(youtube_id=youtube_id))
    html = response.text

    start = html.rfind('"viewCount"') + 13
    end = html.find('"', start)
    # print(start, end, html[start:end])
    view_count = int(html[start:end])

    start = html.rfind('{"iconType":"LIKE"},"defaultText":{"accessibility":{"accessibilityData":{"label":"') + 82
    end = html.find(' ', start)
    likes = html[start:end]
    if 'no' in likes:
        likes = -1
    else:
        try:
            likes = int(re.sub(',', '', likes))
        except:
            likes = -1

    start = html.rfind('{"iconType":"DISLIKE"},"defaultText":{"accessibility":{"accessibilityData":{"label":"') + 85
    end = html.find(' ', start)
    dislikes = html[start:end]

    if 'no' in dislikes:
        dislikes = -1
    else:
        try:
            dislikes = int(re.sub(',', '', dislikes))
        except:
            dislikes = -1

    yield [view_count, likes, dislikes]

    session_token = find_value(html, 'XSRF_TOKEN', 3)

    data = json.loads(find_value(html, 'window["ytInitialData"] = ', 0, '\n').rstrip(';'))
    for renderer in search_dict(data, 'itemSectionRenderer'):
        ncd = next(search_dict(renderer, 'nextContinuationData'), None)
        if ncd:
            break
    try:
        continuations = [(ncd['continuation'], ncd['clickTrackingParams'])]
    except:
        return

    count = 0
    while continuations:
        print(count)
        continuation, itct = continuations.pop()
        response = ajax_request(session, YOUTUBE_COMMENTS_AJAX_URL_NEW,
                                params={'action_get_comments': 1,
                                        'pbj': 1,
                                        'ctoken': continuation,
                                        'continuation': continuation,
                                        'itct': itct},
                                data={'session_token': session_token},
                                headers={'X-YouTube-Client-Name': '1',
                                         'X-YouTube-Client-Version': '2.20200207.03.01'})

        if not response:
            break
        if list(search_dict(response, 'externalErrorMessage')):
            raise RuntimeError('Error returned from server: ' + next(search_dict(response, 'externalErrorMessage')))

        # Ordering matters. The newest continuations should go first.
        continuations = [(ncd['continuation'], ncd['clickTrackingParams'])
                         for ncd in search_dict(response, 'nextContinuationData')] + continuations

        for comment in search_dict(response, 'commentRenderer'):
            if "." in comment['commentId']:  # 답글 패스
                continue
            try:
                text = ''.join([c['text'] for c in comment['contentText']['runs']])
            except:
                continue
            yield {'cid': comment['commentId'],
                   'text': text,
                   'time': comment['publishedTimeText']['runs'][0]['text'],
                   'author': comment.get('authorText', {}).get('simpleText', ''),
                   'channel': comment['authorEndpoint']['browseEndpoint']['browseId'],
                   'votes': comment.get('voteCount', {}).get('simpleText', '0'),
                   'photo': comment['authorThumbnail']['thumbnails'][-1]['url']}
            count += 1
            if count >= 100:
                continuations = None
                break

        time.sleep(1)


def search_dict(partial, key):
    if isinstance(partial, dict):
        for k, v in partial.items():
            if k == key:
                yield v
            else:
                for o in search_dict(v, key):
                    yield o
    elif isinstance(partial, list):
        for i in partial:
            for o in search_dict(i, key):
                yield o


def download_comments_old_api(youtube_id, sleep=1):
    # Use the old youtube API to download all comments (does not work for live streams)
    session = requests.Session()
    session.headers['User-Agent'] = USER_AGENT
    session.cookies.set_cookie(cookies)

    # Get Youtube page with initial comments
    response = session.get(YOUTUBE_VIDEO_URL.format(youtube_id=youtube_id))
    html = response.text
    # print(html)
    # raise Exception
    start = html.rfind('"viewCount"') + 13
    end = html.find('"', start)
    # print(start, end, html[start:end])

    if 'html' in html[start:end]:
        conn = pg2.connect(database="createtrend", user="muna", password="muna112358!", host="222.112.206.190",
                           port="5432")
        conn.autocommit = False
        cur = conn.cursor()
        sql = f"UPDATE video SET forbidden = TRUE WHERE video_id = '{youtube_id}'"
        print("Unavailabel video")
        cur.execute(sql)
        conn.commit()
        conn.close()
        return

    view_count = int(html[start:end])

    start = html.rfind('{"iconType":"LIKE"},"defaultText":{"accessibility":{"accessibilityData":{"label":"') + 82
    end = html.find(' ', start)
    likes = html[start:end]
    if 'no' in likes:
        likes = -1
    else:
        try:
            likes = int(re.sub(',', '', likes))
        except:
            likes = -1

    start = html.rfind('{"iconType":"DISLIKE"},"defaultText":{"accessibility":{"accessibilityData":{"label":"') + 85
    end = html.find(' ', start)
    dislikes = html[start:end]

    if 'no' in dislikes:
        dislikes = -1
    else:
        try:
            dislikes = int(re.sub(',', '', dislikes))
        except:
            dislikes = -1

    yield [view_count, likes, dislikes]

    reply_cids = extract_reply_cids(html)

    ret_cids = []
    for comment in extract_comments(html):
        ret_cids.append(comment['cid'])
        yield comment

    page_token = find_value(html, 'data-token')
    session_token = find_value(html, 'XSRF_TOKEN', 3)

    first_iteration = True

    count = 0
    # print('old')
    # Get remaining comments (the same as pressing the 'Show more' button)
    while page_token:
        # print(count)
        data = {'video_id': youtube_id,
                'session_token': session_token}

        params = {'action_load_comments': 1,
                  'order_by_time': False,
                  'filter': youtube_id}

        if first_iteration:
            params['order_menu'] = True
        else:
            data['page_token'] = page_token

        response = ajax_request(session, YOUTUBE_COMMENTS_AJAX_URL_OLD, params, data)
        if not response:
            break

        page_token, html = response.get('page_token', None), response['html_content']

        reply_cids += extract_reply_cids(html)
        for comment in extract_comments(html):
            if comment['cid'] not in ret_cids:
                ret_cids.append(comment['cid'])
                yield comment
                count += 1
                if count >= 100:
                    page_token = None
                    break

        first_iteration = False
        time.sleep(sleep)

    # Get replies (the same as pressing the 'View all X replies' link)
    # for cid in reply_cids:
    #     data = {'comment_id': cid,
    #             'video_id': youtube_id,
    #             'can_reply': 1,
    #             'session_token': session_token}
    #
    #     params = {'action_load_replies': 1,
    #               'order_by_time': True,
    #               'filter': youtube_id,
    #               'tab': 'inbox'}
    #
    #     response = ajax_request(session, YOUTUBE_COMMENTS_AJAX_URL_OLD, params, data)
    #     if not response:
    #         break
    #
    #     html = response['html_content']
    #
    #     for comment in extract_comments(html):
    #         if comment['cid'] not in ret_cids:
    #             ret_cids.append(comment['cid'])
    #             yield comment
    #     time.sleep(sleep)


def extract_comments(html):
    tree = lxml.html.fromstring(html)
    item_sel = CSSSelector('.comment-item')
    text_sel = CSSSelector('.comment-text-content')
    time_sel = CSSSelector('.time')
    author_sel = CSSSelector('.user-name')
    vote_sel = CSSSelector('.like-count.off')
    photo_sel = CSSSelector('.user-photo')

    for item in item_sel(tree):
        if "." in item.get('data-cid'):  # 답글 패스
            continue
        yield {'cid': item.get('data-cid'),
               'text': text_sel(item)[0].text_content(),
               'time': time_sel(item)[0].text_content().strip(),
               'author': author_sel(item)[0].text_content(),
               'channel': item[0].get('href').replace('/channel/', '').strip(),
               'votes': vote_sel(item)[0].text_content() if len(vote_sel(item)) > 0 else 0,
               'photo': photo_sel(item)[0].get('src')}


def extract_reply_cids(html):
    tree = lxml.html.fromstring(html)
    sel = CSSSelector('.comment-replies-header > .load-comments')
    return [i.get('data-cid') for i in sel(tree)]


def pre_process_comment(text):
    temp = bytearray(text.encode('UTF-8'))
    temp.replace(b'\x00', b'')
    text = temp.decode('utf-8', 'ignore')
    # re.sub("\"", " ", temp)
    return re.sub("'", "''", text)


def pre_process_write_date(text):
    if 'edited' in text:
        text = text[:text.rfind(' ')]
    return text


def main(video_id):
    # parser = argparse.ArgumentParser(add_help=False,
    #                                  description=('Download Youtube comments without using the Youtube API'))
    # parser.add_argument('--help', '-h', action='help', default=argparse.SUPPRESS,
    #                     help='Show this help message and exit')
    # parser.add_argument('--youtubeid', '-y', help='ID of Youtube video for which to download the comments')
    # parser.add_argument('--output', '-o', help='Output filename (output format is line delimited JSON)')
    # parser.add_argument('--limit', '-l', type=int, help='Limit the number of comments')

    try:
        # args = parser.parse_args(argv)
        youtube_id = video_id
        time_control = True
        do_sql = False
        # output = args.output
        # limit = 100

        # if not youtube_id or not output:
        #     parser.print_usage()
        #     raise ValueError('you need to specify a Youtube ID and an output filename')

        # if os.sep in output:
        #     outdir = os.path.dirname(output)
        #     if not os.path.exists(outdir):
        #         os.makedirs(outdir)

        print('Downloading Youtube comments for video:', youtube_id)
        count = 0
        first = True
        # with io.open(output, 'w', encoding='utf8') as fp:
        sys.stdout.write('Downloaded %d comment(s)\r' % count)
        sys.stdout.flush()
        start_time = time.time()

        conn = pg2.connect(database="createtrend", user="muna", password="muna112358!", host="222.112.206.190",
                           port="5432")
        conn.autocommit = False
        cur = conn.cursor()

        for comment in download_comments(youtube_id):
            # if not do_sql:
            #     print(comment)
            if first:
                view_count, likes, dislikes = comment

                sql = \
                    f"""INSERT INTO video_views (video_idx, views, check_time)
                        VALUES ((SELECT idx FROM video WHERE video_id = '{video_id}'),'{view_count}', CURRENT_TIMESTAMP);
                        INSERT INTO video_likes (video_idx, likes, check_time, dislikes)
                        VALUES ((SELECT idx FROM video WHERE video_id = '{video_id}'),'{likes}', CURRENT_TIMESTAMP, '{dislikes}');"""
                if do_sql:
                    cur.execute(sql)

                first = False
                continue

            sql = f"""
                        DO
                        $$
                            DECLARE
                                var_video_idx   integer;
                                var_comment_idx integer;
                            BEGIN
                                SELECT idx INTO var_video_idx FROM video WHERE video_id = '{video_id}'; -- video_idx 확보

                                SELECT idx -- comment_idx 확보 (존재한다면)
                                INTO var_comment_idx
                                FROM comment
                                WHERE comment_id = '{comment['cid']}'
                                  AND video_idx = var_video_idx;


                                IF var_comment_idx IS NULL THEN -- comment가 존재하지 않는다면
                                    INSERT INTO comment (video_idx, comment_content, write_time, writer_name, comment_id, writer_img_url)
                                    VALUES (var_video_idx, '{pre_process_comment(comment['text'])}', CURRENT_TIMESTAMP + INTERVAL'{pre_process_write_date(comment['time'])}', 
                                    '{pre_process_comment(comment['author'])}', '{comment['cid']}', '{comment['photo']}')
                                    RETURNING idx INTO var_comment_idx;
                                END IF;

                                INSERT INTO comment_likes (comment_idx, likes, check_time)
                                VALUES (var_comment_idx, '{comment['votes']}', CURRENT_TIMESTAMP);
                            END
                        $$;"""
            if do_sql:
                cur.execute(sql)

            count += 1
            sys.stdout.write('Downloaded %d comment(s)\r' % count)
            sys.stdout.flush()

        if do_sql:
            conn.commit()
        conn.close()

        if time_control:
            time_interval = time.time() - start_time

            if time_interval <= 6:  # 속도 조절
                time.sleep(6 - time_interval + random.random())

        print('\n[{:.2f} seconds] Done!'.format(time.time() - start_time))
        return True

    except Exception as e:
        print(traceback.format_exc())
        print('Error:', str(e))

        if time_control:
            time_interval = time.time() - start_time
            if time_interval <= 6:  # 속도 조절
                time.sleep(6 - time_interval + random.random())

        print('\n[{:.2f} seconds] Done!'.format(time.time() - start_time))
        return False
        # sys.exit(1)


if __name__ == "__main__":
    main('GMjc7Cc51ao')