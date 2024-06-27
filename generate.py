import argparse
import math
import os
from pathlib import Path
import subprocess
import shlex
import tempfile
import shutil

def parse_args():
    parser = argparse.ArgumentParser()
    # we accept multiple video file paths
    parser.add_argument("video_paths", nargs="+", type=Path, help="Paths to video files")
    parser.add_argument("--output", "-o", type=Path, help="Output file path", default="output.mp4")
    return parser.parse_args()

def get_video_length(filename):
    output = subprocess.check_output(("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                      "default=noprint_wrappers=1:nokey=1", filename)).strip()
    video_length = int(float(output))
    print("Video length in seconds: " + str(video_length))

    return video_length

def split_by_seconds(filename:str, split_length:int, vcodec="copy", acodec="copy",
                     extra="", video_length=None, output_folder="", **kwargs):
    if split_length and split_length <= 0:
        print("Split length can't be 0")
        raise SystemExit

    return_paths = []

    if not video_length:
        video_length = get_video_length(filename)
    split_count = ceildiv(video_length, split_length)
    if split_count == 1:
        print("Video length is less then the target split length.")
        raise SystemExit

    split_cmd = ["ffmpeg", "-i", filename, "-vcodec", vcodec, "-acodec", acodec] + shlex.split(extra)
    try:
        filebase = ".".join(filename.split(".")[:-1])
        fileext = filename.split(".")[-1]
        if len(output_folder) > 0:
            filebase = os.path.join(output_folder, filebase)
    except IndexError as e:
        raise IndexError("No . in filename. Error: " + str(e))
    for n in range(0, split_count):
        split_args = []
        if n == 0:
            split_start = 0
        else:
            split_start = split_length * n
        output_path = filebase.replace(" ", "_").lower() + "-" + str(n + 1) + "-of-" + str(split_count) + "." + fileext
        split_args += ["-reset_timestamps", "1", "-ss", str(split_start), "-t", str(split_length), output_path]
        # print("About to run: " + " ".join(split_cmd + split_args))
        subprocess.run(split_cmd + split_args, check=True, capture_output=False)
        return_paths.append(output_path)

    return return_paths

def ceildiv(a, b):
    return int(math.ceil(a / float(b)))

def copy_to_temp_folder(files: list[str], temp_folder: str=None):
    copied_files = []
    if temp_folder is None:
        temp_folder = tempfile.mkdtemp()
    for file in files:
        copied_files.append(shutil.copy(file, temp_folder))
    return copied_files

def split_videos(video_paths: list[Path]):
    # we accept multiple video paths
    video_clips = []
    for video_path in video_paths:
        print(f"Processing {video_path}")
        # generate a temporary file
        temp_dir_str = tempfile.mkdtemp(video_path.stem[0:10])
        # split the video into two minute clips
        files = split_by_seconds(str(video_path), 120, output_folder=temp_dir_str)
        video_clips.extend(files)
    return video_clips

def combine_videos(video_clips: list[str], output_path: str):
    # combine the video clips into a single video
    filelist_path = Path("files.txt")
    with open(filelist_path, "w") as f:
        for video_clip in video_clips:
            f.write(f"file '{video_clip}'\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(filelist_path), "-c", "copy", output_path], check=True)
    filelist_path.unlink()

def generate_clip_list(video_clips: list[str], phase_clips: list[str]):
    phase_index = 0
    for video_clip in video_clips:
        yield phase_clips[phase_index % len(phase_clips)]
        phase_index += 1
        yield video_clip

def correct_video_clips(video_clips: list[str]):
    output_files = []
    # correct the video clips to have the same resolution and frame rate
    for index, video_clip in enumerate(video_clips):
        print(f"Correcting video clip {video_clip} {index + 1}/{len(video_clips)}")
        output_file = str(Path(video_clip).stem + "_corrected.mp4")
        ret = subprocess.run(["ffmpeg", "-i", video_clip, "-vf", "scale=1280:720", "-r", "30", "-video_track_timescale", "1000", output_file], capture_output=False)
        if ret.returncode != 0:
            print(f"Failed to correct video clip {video_clip}")
            # print(ret.stderr.split("\\n"))
            # print(ret.stdout.split("\\n"))
            raise SystemExit()
        output_files.append(output_file)
    return output_files

def main():
    # Your code here
    args = parse_args()
    output_path = args.output
    output_path.unlink(missing_ok=True)
    print("Splitting video files")
    source_video_clips = correct_video_clips(split_videos(args.video_paths))
    phase_video_clips = correct_video_clips(copy_to_temp_folder(["phases/voice.mp4", "phases/touch.mp4", "phases/hold.mp4"]))

    output_video_clips = list(generate_clip_list(source_video_clips, phase_video_clips))
    print(output_video_clips)
    print("Combining video clips")
    combine_videos(output_video_clips, output_path)

if __name__ == "__main__":
    main()