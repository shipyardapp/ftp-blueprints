import os
import io
import re
import json
import tempfile
import argparse
import code
import sys

import ftplib

EXIT_CODE_INCORRECT_CREDENTIALS = 3
EXIT_CODE_NO_MATCHES_FOUND = 200


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--source-file-name-match-type',
        dest='source_file_name_match_type',
        choices={
            'exact_match',
            'regex_match'},
        required=True)
    parser.add_argument('--source-folder-name',
                        dest='source_folder_name', default='', required=False)
    parser.add_argument('--source-file-name',
                        dest='source_file_name', required=True)
    parser.add_argument(
        '--destination-file-name',
        dest='destination_file_name',
        default=None,
        required=False)
    parser.add_argument(
        '--destination-folder-name',
        dest='destination_folder_name',
        default='',
        required=False)
    parser.add_argument('--host', dest='host', default=None, required=True)
    parser.add_argument('--port', dest='port', default=21, required=True)
    parser.add_argument(
        '--username',
        dest='username',
        default=None,
        required=False)
    parser.add_argument(
        '--password',
        dest='password',
        default=None,
        required=False)
    return parser.parse_args()


def extract_file_name_from_source_full_path(source_full_path):
    """
    Use the file name provided in the source_file_name variable. Should be run only
    if a destination_file_name is not provided.
    """
    destination_file_name = os.path.basename(source_full_path)
    return destination_file_name


def enumerate_destination_file_name(destination_file_name, file_number=1):
    """
    Append a number to the end of the provided destination file name.
    Only used when multiple files are matched to, preventing the destination file from being continuously overwritten.
    """
    if re.search(r'\.', destination_file_name):
        destination_file_name = re.sub(
            r'\.', f'_{file_number}.', destination_file_name, 1)
    else:
        destination_file_name = f'{destination_file_name}_{file_number}'
    return destination_file_name


def determine_destination_file_name(
    *,
    source_full_path,
    destination_file_name,
        file_number=None):
    """
    Determine if the destination_file_name was provided, or should be extracted from the source_file_name,
    or should be enumerated for multiple file downloads.
    """
    if destination_file_name:
        if file_number:
            destination_file_name = enumerate_destination_file_name(
                destination_file_name, file_number)
        else:
            destination_file_name = destination_file_name
    else:
        destination_file_name = extract_file_name_from_source_full_path(
            source_full_path)

    return destination_file_name


def clean_folder_name(folder_name):
    """
    Cleans folders name by removing duplicate '/' as well as leading and trailing '/' characters.
    """
    folder_name = folder_name.strip('/')
    if folder_name != '':
        folder_name = os.path.normpath(folder_name)
    return folder_name


def combine_folder_and_file_name(folder_name, file_name):
    """
    Combine together the provided folder_name and file_name into one path variable.
    """
    combined_name = os.path.normpath(
        f'{folder_name}{"/" if folder_name else ""}{file_name}')
    combined_name = os.path.normpath(combined_name)

    return combined_name


def determine_destination_name(
        destination_folder_name,
        destination_file_name,
        source_full_path,
        file_number=None):
    """
    Determine the final destination name of the file being downloaded.
    """
    destination_file_name = determine_destination_file_name(
        destination_file_name=destination_file_name,
        source_full_path=source_full_path,
        file_number=file_number)
    destination_name = combine_folder_and_file_name(
        destination_folder_name, destination_file_name)
    return destination_name


def find_files_in_directory(
        client,
        folder_filter,
        files,
        folders):
    """
    Pull in a list of all entities under a specific directory and categorize them into files and folders.
    """
    original_dir = client.pwd()
    names = client.nlst(folder_filter)
    for name in names:
        # Accounts for an issue where some FTP servers return file names
        # without folder prefixes.
        if '/' not in name:
            name = f'{folder_filter}/{name}'

        try:
            client.cwd(name)
            # If you can change the directory to the entity_name, it's a
            # folder.
            folders.append(f'{name}')
        except ftplib.error_perm as e:
            files.append(f'{name}')  # If you can't, it's a file.
            continue
        client.cwd(original_dir)

    folders.remove(folder_filter)

    return files, folders


def find_matching_files(file_names, file_name_re):
    """
    Return a list of all file_names that matched the regular expression.
    """
    matching_file_names = []
    for file_name in file_names:
        fname = file_name.rsplit('/', 1)[-1]
        if re.search(file_name_re, fname):
            matching_file_names.append(file_name)

    return matching_file_names


def download_ftp_file(client, file_name, destination_file_name=None):
    """
    Download a selected file from the FTP server to local storage in
    the current working directory or specified path.
    """
    local_path = os.path.normpath(f'{os.getcwd()}/{destination_file_name}')
    path = local_path.rsplit('/', 1)[0]
    if not os.path.exists(path):
        os.mkdir(path)
    try:
        with open(local_path, 'wb') as f:
            client.retrbinary(f'RETR {file_name}', f.write)
    except Exception as e:
        os.remove(local_path)
        print(f'Failed to download {file_name}')
        raise(e)

    print(f'{file_name} successfully downloaded to {local_path}')
    return


def get_client(host, port, username, password):
    """
    Attempts to create an FTP client at the specified hots with the
    specified credentials
    """
    try:
        client = ftplib.FTP(timeout=3600)
        client.connect(host, int(port))
        client.login(username, password)
        client.set_pasv(True)
        client.set_debuglevel(0)
        return client
    except Exception as e:
        print(f'Error accessing the FTP server with the specified credentials')
        print(f'The server says: {e}')
        sys.exit(EXIT_CODE_INCORRECT_CREDENTIALS)


def main():
    args = get_args()
    host = args.host
    port = args.port
    username = args.username
    password = args.password
    source_file_name = args.source_file_name
    source_folder_name = clean_folder_name(args.source_folder_name)
    source_full_path = combine_folder_and_file_name(
        folder_name=source_folder_name, file_name=source_file_name)
    source_file_name_match_type = args.source_file_name_match_type

    destination_folder_name = clean_folder_name(args.destination_folder_name)
    if not os.path.exists(destination_folder_name) and \
            (destination_folder_name != ''):
        os.makedirs(destination_folder_name)

    client = get_client(host=host, port=port, username=username,
                        password=password)
    if source_file_name_match_type == 'regex_match':
        folders = [source_folder_name]
        files = []
        while folders != []:

            folder_filter = folders[0]
            files, folders = find_files_in_directory(
                client=client, folder_filter=folder_filter, files=files, folders=folders)

        matching_file_names = find_matching_files(files,
                                                  re.compile(source_file_name))

        number_of_matches = len(matching_file_names)

        if number_of_matches == 0:
            print(f'No matches were found for regex "{source_file_name}".')
            sys.exit(EXIT_CODE_NO_MATCHES_FOUND)

        print(f'{len(matching_file_names)} files found. Preparing to download...')

        for index, file_name in enumerate(matching_file_names):
            destination_name = determine_destination_name(
                destination_folder_name=destination_folder_name,
                destination_file_name=args.destination_file_name,
                source_full_path=file_name, file_number=index + 1)

            print(f'Downloading file {index+1} of {len(matching_file_names)}')
            try:
                download_ftp_file(client=client, file_name=file_name,
                                  destination_file_name=destination_name)
            except Exception as e:
                print(f'Failed to download {file_name}... Skipping')
    else:
        destination_name = determine_destination_name(
            destination_folder_name=destination_folder_name,
            destination_file_name=args.destination_file_name,
            source_full_path=source_full_path)

        try:
            download_ftp_file(client=client, file_name=source_full_path,
                              destination_file_name=destination_name)
        except Exception as e:
            print(f'The server says: {e}')
            print(f'Most likely, the file name/folder name you specified has typos or the full folder name was not provided. Check these and try again.')
            sys.exit(EXIT_CODE_NO_MATCHES_FOUND)


if __name__ == '__main__':
    main()
