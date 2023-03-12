import os
import shutil
import io
import pickle
import datetime
import time
import uvloop
from IPython.display import clear_output
from pyrogram import Client
from re import search as re_search
from urllib.parse import parse_qs, urlparse
from os import makedirs, path as ospath, listdir, remove as osremove
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload


uvloop.install()


api_id = 14269266
api_hash = "d454cd5c47a4cea89b6ce7448c532fc4"
# bot_token = "5558586331:AAHcUlXjsECwp8UkreX7KgqelH0X_oXfTjc"
bot_token = "5611075507:AAHK2qJMsqfryprRAlYgW2GB0vgokJjlu00"
dump_id = -1001578391154
chat_id = 1564082459
# Replace THUMB_PATH with the path to your thumbnail file (optional)
thumb_path = "/content/thmb.jpg"

# Replace FILE_PATH with the path to your media file
d_path = "/content/Downloads"


# =================================================================
#    G Drive Functions
# =================================================================


# extract the file ID or folder ID from the link
def __getIdFromUrl(link: str):
    if "folders" in link or "file" in link:
        regex = r"https:\/\/drive\.google\.com\/(?:drive(.*?)\/folders\/|file(.*?)?\/d\/)([-\w]+)"
        res = re_search(regex, link)
        if res is None:
            raise IndexError("G-Drive ID not found.")
        return res.group(3)
    parsed = urlparse(link)
    return parse_qs(parsed.query)["id"][0]


def __getFilesByFolderId(folder_id):
    page_token = None
    files = []
    while True:
        response = (
            service.files()
            .list(
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                q=f"'{folder_id}' in parents and trashed = false",
                spaces="drive",
                pageSize=200,
                fields="nextPageToken, files(id, name, mimeType, size, shortcutDetails)",
                orderBy="folder, name",
                pageToken=page_token,
            )
            .execute()
        )
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if page_token is None:
            break
    return files


def __getFileMetadata(file_id):
    return (
        service.files()
        .get(fileId=file_id, supportsAllDrives=True, fields="name, id, mimeType, size")
        .execute()
    )


def get_time():
    currentDateAndTime = datetime.datetime.now()
    currentTime = currentDateAndTime.strftime("%H:%M:%S")
    return currentTime


# async def edit_msg(msg, text):
#     async with Client(
#         "my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token
#     ) as bot:
#         await bot.edit_message_text(chat_id=chat_id, message_id=msg.id, text=text)


async def __download_file(file_id, path):
    # Check if the specified file or folder exists and is downloadable.
    try:
        file = service.files().get(fileId=file_id, supportsAllDrives=True).execute()
    except HttpError as error:
        print("An error occurred: {0}".format(error))
        file = None
    if file is None:
        print(
            "Sorry, the specified file or folder does not exist or is not accessible."
        )
    else:
        if file["mimeType"].startswith("application/vnd.google-apps"):
            print(
                "Sorry, the specified ID is for a Google Docs, Sheets, Slides, or Forms document. You can only download these types of files in specific formats."
            )
        else:
            # Create a BytesIO stream to hold the downloaded file data.
            file_contents = io.BytesIO()

            # Download the file or folder contents to the BytesIO stream.
            request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
            file_downloader = MediaIoBaseDownload(file_contents, request)
            done = False
            while done is False:
                status, done = file_downloader.next_chunk()
                print(f"Download progress: {int(status.progress() * 100)}%")
            file_contents.seek(0)

            # Save the downloaded file or folder to disk using its original name (if available).
            file_name = file.get("name", f"untitleddrivefile_{file_id}")
            file_name = os.path.join(path, file_name)
            with open(file_name, "wb") as handle:
                handle.write(file_contents.getbuffer())
            di_text = f"{os.path.basename(file_name)} => Downloaded !"
            print(di_text)
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg.id,
                text=down_msg + di_text,
            )


# Usage example
# __download_file('1XQyVFHC44zso-HM2-EyLm8YeusxcqNOX', '/content/Downloads')


async def __download_folder(folder_id, path):

    folder_meta = __getFileMetadata(folder_id)
    folder_name = folder_meta["name"]
    if not ospath.exists(f"{path}/{folder_name}"):
        makedirs(f"{path}/{folder_name}")
    path += f"/{folder_name}"
    result = __getFilesByFolderId(folder_id)
    if len(result) == 0:
        return
    result = sorted(result, key=lambda k: k["name"])
    for item in result:
        file_id = item["id"]
        shortcut_details = item.get("shortcutDetails")
        if shortcut_details is not None:
            file_id = shortcut_details["targetId"]
            mime_type = shortcut_details["targetMimeType"]
        else:
            mime_type = item.get("mimeType")
        if mime_type == "application/vnd.google-apps.folder":
            await __download_folder(file_id, path)
        else:
            await __download_file(file_id, path)


# =================================================================
#    Telegram Upload Functions
# =================================================================


def get_file_type(file_path):
    name, extension = os.path.splitext(file_path)
    if extension in [".mp4", ".avi", ".mkv", ".mov", ".webm", ".m4v"]:
        video_extension_fixer(file_path)
        return "video"
    elif extension in [".mp3", ".wav", ".flac", ".aac", ".ogg"]:
        return "audio"
    elif extension in [".jpg", ".jpeg", ".png", ".gif"]:
        return "photo"
    else:
        return "document"


def video_extension_fixer(file_path):

    dir_path, filename = os.path.split(file_path)

    if filename.endswith(".mp4") or filename.endswith(".mkv"):
        pass
    # split the file name and the extension
    else:
        # rename the video file with .mp4 extension
        name, ext = os.path.splitext(filename)
        os.rename(
            os.path.join(dir_path, filename), os.path.join(dir_path, name + ".mp4")
        )
        print(f"{filename} was changed to {name}.mp4")


def create_zip(folder_path):
    folder_name = os.path.basename(folder_path)  # get folder name from folder path
    zip_file_path = folder_path  # create zip file path
    shutil.make_archive(
        zip_file_path, "zip", folder_path
    )  # create zip file by archiving the folder
    return zip_file_path + ".zip"  # return zip file path


async def size_checker(file_path):

    max_size = 2097152000  # 2 GB
    file_size = os.stat(file_path).st_size

    if file_size > max_size:

        print(f"File size is {file_size / (1024 * 1024):.2f} MB. SPLITTING.......")

        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg.id,
            text=down_msg
            + f"\nSIZE: {file_size / (1024 * 1024):.2f} MB\n\n<b>SO SPLITTING !</b>",
        )

        if not ospath.exists(d_fol_path):
            makedirs(d_fol_path)

        split_zipFile(file_path, max_size)

        return True
    else:

        print(f"File size is {file_size / (1024 * 1024):.2f} MB. NOT SPLITTING.......")
        return False


def split_zipFile(file_path, max_size):

    dir_path, filename = os.path.split(file_path)

    new_path = f"{d_fol_path}/{filename}"

    with open(file_path, "rb") as f:
        chunk = f.read(max_size)
        i = 1

        while chunk:
            # Generate filename for this chunk
            ext = str(i).zfill(3)
            output_filename = "{}.{}".format(new_path, ext)

            # Write chunk to file
            with open(output_filename, "wb") as out:
                out.write(chunk)

            # Get next chunk
            chunk = f.read(max_size)

            # Increment chunk counter
            i += 1


def is_time_over(current_time):
    ten_sec_passed = time.time() - current_time[0] >= 6
    if ten_sec_passed:
        current_time[0] = time.time()
    return ten_sec_passed


async def progress_bar(current, total):

    speed_string = ""

    if current > 0:
        elapsed_time_seconds = (datetime.datetime.now() - start_time).seconds
        upload_speed = current / elapsed_time_seconds
        upload_speed /= 1024 * 1024
        speed_string = f"{upload_speed:.2f} MB/s"

    percentage = round(current / total * 100, 2)
    bar_length = 10
    filled_length = int(percentage / 100 * bar_length) 
    bar = "⬢" * filled_length + "⬡" * (bar_length - filled_length)
    message = f"\n[{bar}] {percentage}%\n\nDONE: __{current / (1024 * 1024):.2f}__ OF __{total / (1024 * 1024):.2f}__ MB  __{speed_string}__"
    try:
        print(message)
        # Edit the message with updated progress information.
        if is_time_over(current_time):
            await bot.edit_message_text(
                chat_id=chat_id, message_id=msg.id, text=text_msg + message
            )

    except Exception as e:
        # Catch any exceptions that might occur while editing the message.
        print(f"Error updating progress bar: {str(e)}")


async def upload_file(file_path, type, file_name):

    # Upload the file
    try:

        caption = f"<code>{file_name}</code>"

        if type == "video":

            sent = await bot.send_video(
                chat_id=dump_id,
                video=file_path,
                supports_streaming=True,
                width=480,
                height=320,
                caption=caption,
                thumb=thumb_path,
                progress=progress_bar,
            )

        elif type == "audio":

            sent = await bot.send_audio(
                chat_id=dump_id,
                audio=file_path,
                supports_streaming=True,
                caption=caption,
                thumb=thumb_path,
                progress=progress_bar,
            )

        elif type == "document":

            sent = await bot.send_document(
                chat_id=dump_id,
                document=file_path,
                caption=caption,
                thumb=thumb_path,
                progress=progress_bar,
            )

        elif type == "photo":

            sent = await bot.send_photo(
                chat_id=dump_id,
                photo=file_path,
                caption=caption,
                progress=progress_bar,
            )

        clear_output()

        sent_file.append(sent)
        sent_fileName.append(file_name)
        print(f"\n{file_name} Sent !")

    except Exception as e:
        print(e)


# ****************************************************************
#    Main Functions, function calls and variable declarations
# ****************************************************************


if not ospath.exists(d_path):
    makedirs(d_path)

# create credentials object from token.pickle file
creds = None
if os.path.exists("/content/token.pickle"):
    with open("/content/token.pickle", "rb") as token:
        creds = pickle.load(token)
else:
    exit(1)

# create drive API client
service = build("drive", "v3", credentials=creds)


# enter the link for the file or folder that you want to download
link = input("Enter the Google Drive link for the file or folder: ")

file_id = __getIdFromUrl(link)

meta = __getFileMetadata(file_id)

d_name = meta["name"]

d_fol_path = f"{d_path}/{d_name}"

sent_file = []
sent_fileName = []

async with Client(
    "my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token
) as bot:

    down_msg = f"<b>DOWNLOADING: </b>\n\n<code>{d_name}</code>\n\n<b>Files LOG: </b>\n\n"

    try:
        msg = await bot.send_message(chat_id=chat_id, text=down_msg)
    except Exception as e:
        print(f"Can not {e} ")

    # Determine if the ID is of file or folder
    if meta.get("mimeType") == "application/vnd.google-apps.folder":
        await __download_folder(file_id, d_path)
        clear_output()
        print("*" * 40 + "\n Folder Download Complete\n" + "*" * 40)

    else:
        if not ospath.exists(d_fol_path):
            makedirs(d_fol_path)
        await __download_file(file_id, d_fol_path)
        clear_output()
        print("*" * 40 + "\n File Download Complete\n" + "*" * 40)

    down_msg = f"\n<b>Download COMPLETE:</b>\n\n<code>{d_name}</code>\n"

    msg = await bot.edit_message_text(
        chat_id=chat_id,
        message_id=msg.id,
        text=down_msg + f"\nNow ZIPPING !",
    )

    print("\nNow Zipping the folder...")
    z_file_path = create_zip(d_fol_path)
    print(f"\nZip file saved as: {z_file_path}")


    shutil.rmtree(d_fol_path)
    print("\nDELETED Original Directory !\n")

    msg = await bot.edit_message_text(
        chat_id=chat_id,
        message_id=msg.id,
        text=down_msg
        + f"\nNow Checking The FILE for Leech",
    )

    leech = await size_checker(z_file_path)

    file_size = os.stat(z_file_path).st_size

    clear_output()

    current_time = []
    current_time.append(time.time())

    if leech:  # File was splitted

        if ospath.exists(z_file_path):
            os.remove(z_file_path)  # Delete original Big Zip file
        print("Big Zip File Deleted !")
        # print('\nNow uploading multiple splitted zip files..........\n')

        dir_list = sorted(os.listdir(d_fol_path))

        count = 1

        for dir_path in dir_list:

            short_path = os.path.join(d_fol_path, dir_path)
            file_type = get_file_type(short_path)
            file_name = os.path.basename(short_path)
            print(f"\nNow uploading {file_name}\n")
            start_time = datetime.datetime.now()
            current_time[0] = time.time()
            text_msg = f"<b>UPLOADING: {count} OF {len(dir_list)} Files</b>\n\n<code>{file_name}</code>\n"
            msg = await bot.edit_message_text(
                chat_id=chat_id, message_id=msg.id, text=text_msg
            )
            await upload_file(short_path, file_type, file_name)

            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg.id,
                text=f"<b>UPLOAD COMPLETE:</b>\n\n<code>{file_name}</code>\n",
            )
            
            count += 1

        shutil.rmtree(d_fol_path)

    else:

        file_type = get_file_type(z_file_path)
        file_name = os.path.basename(z_file_path)
        print(f"\nNow uploading {file_name}\n")
        start_time = datetime.datetime.now()
        current_time[0] = time.time()
        text_msg = f"<b>UPLOADING:</b>\n\n<code>{file_name}</code>\n"
        msg = await bot.edit_message_text(
            chat_id=chat_id, message_id=msg.id, text=text_msg
        )
        await upload_file(short_path, file_type, file_name)

        os.remove(z_file_path)


    final_text = f"<b>UPLOAD COMPLETE:</b>\n\n<code>{d_name}</code>\n"
    i = 0

    for sent in sent_file:

        file_link = f"https://t.me/c/1578391154/{sent.id}"
        fileName = sent_fileName[i]
        fileText = f"\n{i+1} - <a href={file_link}>{fileName}</a>"
        final_text += fileText
        i += 1

    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=msg.id,
        text=final_text
    )
