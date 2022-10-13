import os
import re
import argparse
import sys
import shutil
import shipyard_utils as shipyard
import ftplib
try:
    import exit_codes as ec
except BaseException:
    from . import exit_codes as ec


def get_args():
    parser = argparse.ArgumentParser()
    
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
    parser.add_argument('--file-name-match-type',
                        dest='file_name_match_type',
                        choices={
                            'exact_match',
                            'regex_match'},
                        required=False,
                        default = 'exact_match')
    parser.add_argument('--source-file-name', 
                        dest='source_file_name',
                        required=True)
    parser.add_argument('--source-folder-name',
                        dest='source_folder_name',
                        default='', required=False)
    return parser.parse_args()


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
            folders.append(name)
        except ftplib.error_perm as e:
            files.append(name)  # If you can't, it's a file.
            continue
        client.cwd(original_dir)

    folders.remove(folder_filter)

    return files, folders


def delete_ftp_file(client, folder_name, file_name):
    """
    Delete a selected file from the FTP server.
    """
    current_dir = client.pwd()
    target = os.path.join(current_dir,folder_name,file_name)
    target_norm = os.path.normpath(target)
    try:
        # client.ftpObject.cwd(folder_name)
        # client.ftpObject.delete(file_name)
        client.delete(target_norm)
        print(f'Successfully deleted {file_name}')
    except Exception as e:
        print(f'Failed to delete file {target_norm}. Ensure that the folder path and file name our correct') 
        sys.exit(ec.EXIT_CODE_INVALID_FILE_PATH)
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
        sys.exit(ec.EXIT_CODE_INCORRECT_CREDENTIALS)


def main():
    args = get_args()
    host = args.host
    port = args.port
    username = args.username
    password = args.password
    file_name_match_type = args.file_name_match_type
    file_name = args.source_file_name
    folder_name = shipyard.files.clean_folder_name(args.source_folder_name)
    
    client = get_client(host=host, port=port, username=username,
                        password=password)
                        
    if file_name_match_type == 'regex_match':
        folders = [folder_name]
        files = []
        while folders != []:
            folder_filter = folders[0]
            files, folders = find_files_in_directory(
                client=client, folder_filter=folder_filter, files=files, folders=folders)

        matching_file_names = shipyard.files.find_all_file_matches(files,
                                                  re.compile(file_name))

        number_of_matches = len(matching_file_names)

        if number_of_matches == 0:
            print(f'No matches were found for regex "{file_name}".')
            sys.exit(ec.EXIT_CODE_NO_MATCHES_FOUND)

        for index, file_name in enumerate(matching_file_names):
            
            print(f'Deleting file {index+1} of {len(matching_file_names)} out of {number_of_matches}')
            try:
                delete_ftp_file(client=client, folder_name=folder_name, file_name=file_name)
            except Exception as e:
                print(f'Failed to delete {file_name}... Skipping')
    else:
        try:
            delete_ftp_file(client=client, folder_name=folder_name, file_name=file_name)
        except Exception as e:
            print(f'The server says: {e}')
            print(f'Most likely, the file name/folder name you specified has typos or the full folder name was not provided. Check these and try again.')
            sys.exit(ec.EXIT_CODE_NO_MATCHES_FOUND)


if __name__ == '__main__':
    main()