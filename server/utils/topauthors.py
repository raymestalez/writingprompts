import os, sys
import json
import pickle
import praw
from praw.models import Comment, User
from datetime import datetime 
from dateutil.relativedelta import relativedelta 
from retrying import retry


# Connect to praw
def connect():
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    r = praw.Reddit(
        client_id = config["client_id"],
        client_secret = config["client_secret"],
        user_agent='Best /r/WritingPrompts authors by /u/raymestalez'
    )
    return r


# Convert timestamp to age
def age(timestamp):
    dt1 = datetime.fromtimestamp(timestamp)
    dt2 = datetime.now()
    rd = relativedelta(dt2, dt1)
    age =  "%d days, %d hours" % (rd.days, rd.hours)
    return age

# Execute a function, retry if fails, and save results into a file
@retry(stop_max_attempt_number=10)
def cache(function, argument_dict, filename, refetch=False):
    filename = './cache/'+filename
    print(filename)
    if os.path.isfile(filename) and not refetch:
        # If there's a file, and I'm not telling it to refetch, I just read from file
        print("Reading from file " + filename)
        with open (filename, 'rb') as fp:
            results = pickle.load(fp)
        return results
    else:
        # On the first run, or if I want to refetch - execute the passed function
        # And save results into a file
        print("Refetched, writing to file " + filename)            
        results = function(**argument_dict)
        with open(filename, 'wb') as fp:
            pickle.dump(results, fp)
        return results


        
# Grab top posts
def fetch_top_posts(limit=10, time_filter='week'):
    top_posts=list(r.subreddit('writingprompts').top(time_filter=time_filter, limit=limit))
    return top_posts


# Get comments from the top posts, and sort them
def fetch_top_comments(top_posts):
    all_comments = []
    number_of_posts = len(top_posts)
    for index, post in enumerate(top_posts):
        # Looping through posts, taking their comments, adding them all into one list
        real_comments = [c for c in post.comments if isinstance(c, Comment)]
        all_comments += real_comments
        print("Added comments from post: " + str(index) + "/" + str(number_of_posts))

    # Sort comments by score
    sorted_comments = sorted(all_comments, key=lambda x: x.score, reverse=True)
    print("Comments sorted!")

    return sorted_comments

# Put authors of all comments into one list
def extract_authors(comments):
    all_authors = []
    number_of_comments = len(comments)
    for index, comment in enumerate(comments):
        author = comment.author
        # Add author to the list if he's not there yet
        if author and not author in all_authors:
            print("Added to authors: " + author.name)
            print(str(index) + "/" + str(number_of_comments))
            all_authors.append(author)

    print("Authors extracted!")
    return all_authors


@retry(stop_max_attempt_number=10)
def process_author(author, time_filter='week'):
    author.wpscore = 0
    author.beststories = []
    # Combine stories score, collect the best stories.
    comments = author.comments.top(time_filter=time_filter, limit=1000)
    for comment in comments:
        if comment.subreddit.display_name == "WritingPrompts" and comment.is_root:
            author.wpscore += comment.score
            author.beststories.append(comment)

    print('/r/WPs karma calculated: ' + author.name + ' - ' + str(author.wpscore))
    return author


def sort_authors(authors, time_filter='week'):
    # authors = authors[:1000]
    numberofauthors = len(authors)
    processed_authors = []
    for index, author in enumerate(authors):
        try:
            # Combine all author's stories to calculate his total score,
            # and also generate a list of his best stories
            processed_authors.append(process_author(author, time_filter=time_filter))
            print("Processed " + str(index) + "/" + str(numberofauthors))
        except:
            print("Error processing")

    print("All karma calculated.")
    # Sort authors by their /r/WritingPrompts karma
    sorted_authors = sorted(processed_authors, key=lambda x: x.wpscore, reverse=True)
    sorted_authors = sorted_authors[:100]
    print("Authors sorted!")
    print("Last author's karma " + str(sorted_authors[-1].wpscore))
    
    return sorted_authors

def stories_to_json(sorted_stories, max_stories=100, filename="top_stories_all.json"):
    stories_list = []
    
    # Print all keys
    # for key, value in sorted_stories[0].__dict__.items():
    #     print (key)
    # for key, value in sorted_stories[0].author.__dict__.items():
    #     print (key)
    # print(sorted_stories[0]._submission.title)
    # print(sorted_stories[0].author.name)    

    for index, story in enumerate(sorted_stories[:max_stories]):
        # print("Converting story to json " + story._submission.title)
        story_dict = {}
        story_dict['body'] = story.body
        if story.author:
            story_dict['author'] = story.author.name
        story_dict['permalink'] = story.permalink
        story_dict['score'] = story.score                        
        story_dict['prompt'] = story._submission.title.replace('[WP]', '')

        stories_list.append(story_dict)

    # Generate json out of story's list
    stories_json = json.dumps(stories_list)
    print("JSON generated for " + str(len(stories_list)) + " stories")

    filename = './output/'+filename
    with open(filename, "w") as text_file:
        text_file.write(stories_json)


def authors_to_json(sorted_authors, filename):
    authors_list = []
    for index, author in  enumerate(sorted_authors):
        # print("Author " + author.name)
        author_dict = {}
        author_dict['username'] = author.name
        author_dict['karma'] = author.wpscore

        author_dict['beststories'] = []
        for index, story in enumerate(author.beststories[:5]):
            # print("Story score " + str(story.score))
            story_dict = {}
            story_dict['url'] = story.link_url + story.id
            story_dict['prompt'] = story.link_title.replace('[WP]', '')
            author_dict['beststories'].append(story_dict)

        authors_list.append(author_dict)

    # Generate json out of author's list
    authors_json = json.dumps(authors_list)
    print("JSON generated for " + str(len(authors_list)))

    filename = './output/'+filename
    with open(filename, "w") as text_file:
        text_file.write(authors_json)
        

def top_authors(timeframe="all",max_top_posts=1000, max_authors=5000, refetch=True):
    top_posts = cache(
        fetch_top_posts, {'limit': max_top_posts, 'time_filter':'all'},
        'top_posts_'+timeframe+'.pkl', refetch=refetch
    )

    # Combine and sort their comments
    sorted_comments = cache(
        fetch_top_comments, {'top_posts':top_posts},
        'top_comments_'+timeframe+'.pkl', refetch=refetch
    )
    print("Top comments sorted " + str(len(sorted_comments)))
    # Get comment's authors (considering only 5k top stories ever)
    all_authors = cache(
        extract_authors, {'comments':sorted_comments[:5000]},
                        'all_authors_'+timeframe+'.pkl', refetch=refetch
    )
    print("Top authors extracted " + str(len(all_authors)))
    # Sort them in order of combined story karma (considering only first 1k authors)
    sorted_authors = cache(
        sort_authors, {'authors':all_authors[:max_authors],
                       'time_filter':timeframe},
        'sorted_authors_'+timeframe+'.pkl', refetch=refetch
    )

    authors_to_json(sorted_authors, 'top_authors_'+timeframe+'.json')
    

def top_stories(timeframe="all", max_top_posts=1000, refetch=False):
    top_posts = cache(
        fetch_top_posts, {'limit': max_top_posts, 'time_filter':timeframe},
        'top_posts_'+timeframe+'.pkl', refetch=refetch
    )
    sorted_comments = cache(
        fetch_top_comments, {'top_posts':top_posts},
        'top_comments_'+timeframe+'.pkl', refetch=refetch
    )
    stories_to_json(sorted_comments,filename='top_stories_'+timeframe+'.json')

# Doing stuff
r = connect()
subreddit = r.subreddit('writingprompts')

# Test
# top_authors(timeframe="all", max_top_posts=10, max_authors=10, refetch=False)
# top_stories(timeframe="all", max_top_posts=3, refetch=False)
# top_authors(timeframe="week", max_top_posts=10, max_authors=10, refetch=True)
# top_stories(timeframe="week", max_top_posts=10, refetch=False)

# All
top_authors(timeframe="all", max_top_posts=1000, max_authors=5000, refetch=True)
top_stories(timeframe="all", max_top_posts=1000, refetch=False)
# Weekly
top_authors(timeframe="week", max_top_posts=1000, max_authors=5000, refetch=True)
top_stories(timeframe="week", max_top_posts=1000, refetch=False)



