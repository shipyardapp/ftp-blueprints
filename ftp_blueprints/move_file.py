import os
import re
import argparse
import glob
import sys
import shipyard_utils as shipyard
import ftplib
try:
    import exit_codes as ec
except BaseException:
    from . import exit_codes as ec

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-file-name-match-type',
                        dest='source_file_name_match_type',
                        choices={
                            'exact_match',
                            'regex_match'},
                        default='exact_match',
                        required=False)
    parser.add_argument('--source-file-name', dest='source_file_name',
                        required=True)
    parser.add_argument('--source-folder-name', dest='source_folder_name',
                        default='', required=False)
    parser.add_argument(
        '--destination-folder-name',
        dest='destination_folder_name',
        default='',
        required=False)
    parser.add_argument(
        '--destination-file-name',
        dest='destination_file_name',
        default=None,
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


def find_files_in_directory(
        client,
        folder_filter):
    """
    Pull in a list of all entities under a specific directory and categorize them into files and folders.

    Params:
    folder_filter (str) -> the folder path to start searching entities from
    """
    files = []
    folders = []
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
            folders.append(name)
        except ftplib.error_perm:
            files.append(name)  # If you can't, it's a file.
            continue
        client.cwd(original_dir)

    folders.remove(folder_filter)

    return files, folders


def ftp_create_new_folders(client, destination_path):
    """
    Changes working directory to the specified destination path
    and creates it if it doesn't exist
    """
    original_dir = client.pwd()
    for folder in destination_path.split('/'):
        try:
            client.cwd(folder)
        except Exception:
            client.mkd(folder)
            client.cwd(folder)
    client.cwd(original_dir)


def move_ftp_file(
        client,
        source_full_path,
        destination_full_path):
    """
    Move a single file from one directory of the ftp server to another
    """
    # update the file path of the client
    current_dir = client.pwd()
    source_path = os.path.normpath(os.path.join(current_dir,source_full_path))
    dest_path = os.path.normpath(os.path.join(current_dir,destination_full_path))
    # check if source file exists
    # if not os.path.isfile(source_path):
    #     print(f'{source_path} does not exist')
    #     sys.exit(ec.EXIT_CODE_INVALID_FILE_PATH)
    # move files from one path to another
    try:
        client.rename(source_path, dest_path)
    except Exception as e:
        print(f"failed to move {source_path} due to error: {e}")
        sys.exit(ec.EXIT_CODE_FTP_MOVE_ERROR)

    print(f'{source_path} successfully moved to '
          f'{dest_path}')


def get_client(host, port, username, password):
    """
    Attempts to create an FTP client at the specified hots with the
    specified credentials
    """
    try:
        client = ftplib.FTP()
        client.connect(host, int(port))
        client.login(username, password)
        return client
    except Exception as e:
        print(f'Error accessing the FTP server with the specified credentials')
        print(f'The server says: {e}')
        sys.exit(ec.EXIT_CODE_INCORRECT_CREDENTIALS)


def main():
    args = get_args()
    host = args.host
    port = args.port
    username = args.username
    password = args.password
    source_file_name = args.source_file_name
    source_folder_name = args.source_folder_name
    source_full_path = shipyard.files.combine_folder_and_file_name(
        source_folder_name,
        source_file_name)
    destination_folder_name = shipyard.files.clean_folder_name(args.destination_folder_name)
    source_file_name_match_type = args.source_file_name_match_type
    client = get_client(host=host, port=port, username=username,
                        password=password)
    if source_file_name_match_type == 'regex_match':
        file_names, folders = find_files_in_directory(client, source_folder_name)
        matching_file_names = shipyard.files.find_all_file_matches(
            file_names, re.compile(source_file_name))

        number_of_matches = len(matching_file_names)

        if number_of_matches == 0:
            print(f'No matches were found for regex "{source_file_name}".')
            sys.exit(ec.EXIT_CODE_NO_MATCHES_FOUND)

        print(f'{len(matching_file_names)} files found. Preparing to move...')

        for index, key_name in enumerate(matching_file_names):
            destination_full_path = shipyard.files.combine_folder_and_file_name(
                destination_folder_name,
                shipyard.files.extract_file_name_from_source_full_path(key_name)
            )
            if len(destination_full_path.split('/')) > 1:
                path, file_name = destination_full_path.rsplit('/', 1)
                ftp_create_new_folders(client=client, destination_path=path)
            file_name = destination_full_path.rsplit('/', 1)[-1]
            print(f'Moving file {index+1} of {len(matching_file_names)}')
            move_ftp_file(client=client, source_full_path=key_name,
                            destination_full_path=destination_full_path)

    else:
        destination_full_path = shipyard.files.combine_folder_and_file_name(
            destination_folder_name,
            args.destination_file_name,
            )
        if len(destination_full_path.split('/')) > 1:
            path, file_name = destination_full_path.rsplit('/', 1)
            ftp_create_new_folders(client=client, destination_path=path)

        move_ftp_file(client=client, source_full_path=source_full_path,
                        destination_full_path=destination_full_path)


if __name__ == '__main__':
    main()