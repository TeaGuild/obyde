# -*- coding: utf-8 -*-

import yaml
import argparse
import sys
import os
import string
from collections import defaultdict
from .util import parse_obsidian_links, slugify_md_filename
from hashlib import sha256

__all__ = ['main']

def parse_args():
    parser = argparse.ArgumentParser(prog=__package__,
                                     description='Moves and process markdown vaults (mainly Obsidian) to a publishable format')
    parser.add_argument('-c', '--config', type=str, required=True,
                        help='Path to yaml config file. Check config.sample.yaml for an example.')
    return parser.parse_args()


def load_config(config_path):
    try:
        with open(config_path, 'r') as fs:
            config = yaml.safe_load(fs)
            return config
    except:
        raise ValueError(
            'Failed to load configuration. Is the file path correct?')

def dir_exists_or_raise(dirpath, dirpath_type):
    if not os.path.exists(dirpath) or not os.path.isdir(dirpath):
        raise ValueError(f'{dirpath} - {dirpath_type} does not exist or is not a directory')
    return dirpath

def find_files(dirpath, ext=''):
    dirpath = dir_exists_or_raise(dirpath, 'input files location')

    index = defaultdict(set)
    def filefilter(f): return (ext and f.endswith(ext)) or (not ext)

    for root, _, files in os.walk(dirpath):
        filtered_files = filter(filefilter, files)
        for f in filtered_files:
            index[f].add(os.path.join(root, f))

    for x, p in index.items():
        if len(p) > 1:
            filenames = ','.join(p)
            raise ValueError(f'Filename collision detected for {filenames}. This is currently not a supported operating mode.')
    
    cleaned_index = {}

    for x, p in index.items():
        cleaned_index[x] = p.pop()

    return cleaned_index
    
def rewrite_links(content, asset_index, relative_asset_variable):
    obsidian_links = parse_obsidian_links(content)
    rewritten = content
    for link in obsidian_links:
        link_text = link.replace('[[', '').replace(']]', '')
        link_target = link_text
        if '|' in link_text:
            split_link = link_text.split('|')
            link_target = split_link[0]
            link_text = split_link[1] if len(split_link) > 1 else ''
        written = False
        for filename, filepaths in asset_index.items():
            oldpath, newpath = filepaths
            if link_target in filename or link_target in oldpath:
                rewritten = rewritten.replace(link, f'[{link_text}]({relative_asset_variable}/{newpath})')
                written = True
                break
        if not written:
            link_name_slug = slugify_md_filename(link_target)
            rewritten = rewritten.replace(link, f'[{link_text}]({{% post_url {link_name_slug} %}})')
    return rewritten

def write_asset_files(asset_files, asset_output_path):
    modified_file_paths = {}
    for name, path in asset_files.items():
        data = b''
        extension = os.path.splitext(path)[1]
        with open(path, 'rb') as fs:
            data = fs.read()
        hashed_fname = sha256(data).hexdigest() + extension
        asset_path = os.path.join(asset_output_path, hashed_fname)
        if not os.path.exists(asset_path):
            with open(asset_path, 'wb') as out:
                out.write(data)
        modified_file_paths[name] = (path, hashed_fname)
    return modified_file_paths

def process_vault(config):
    md_files = find_files(config['vault']['path'], ext='.md')
    asset_files = find_files(config['vault']['asset_path'])
    post_output_path = dir_exists_or_raise(config['output']['post_output_path'], 'post output path')
    asset_output_path = dir_exists_or_raise(config['output']['asset_output_path'], 'asset output path')
    relative_asset_variable = config['output'].get(
        'relative_asset_variable', 'site.assets_location')

    copied_asset_files = write_asset_files(asset_files, asset_output_path)
    
    for name, path in md_files.items():
        name, ext = os.path.splitext(name)
        slug_name = slugify_md_filename(name) + ext
        with open(path, 'r') as fs:
            rewritten = rewrite_links(fs.read(), copied_asset_files,
                                        relative_asset_variable)
        with open(os.path.join(post_output_path, slug_name),  'w') as out:
            out.write(rewritten)

def main():
    try:
        args = parse_args()
        config = load_config(args.config)
        process_vault(config)
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)