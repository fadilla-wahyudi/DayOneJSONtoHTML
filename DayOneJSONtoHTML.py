import re
import json
import os
from datetime import datetime
import markdown  # pip install markdown
import pytz  # pip install pytz

def normalize_list_boundaries(md_text: str) -> str:
    lines = md_text.splitlines()
    out = []
    prev_blank = True

    list_start_re = re.compile(r'^\s*(?:[-+*]|[0-9]+[.)])\s+')
    for i, line in enumerate(lines):
        is_list_item = bool(list_start_re.match(line))
        # If a list item follows a non-blank line, insert a blank line
        if is_list_item and not prev_blank:
            out.append("")  # blank line to start the list block
        out.append(line)
        prev_blank = (line.strip() == "")
    # Ensure a trailing newline for good measure
    if out and out[-1] != "":
        out.append("")
    return "\n".join(out)


def convert_dayone_json_to_single_html(json_file, photos_dir="photos", videos_dir="videos", audio_dir="audios", output_file="journal.html"):
    # Load JSON data
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    entries_html = ""
    toc_html = ""
    
    # This creates a list to hold formatted dates
    dates = []

    for i, entry in enumerate(data["entries"], start=1):
        text = entry.get("text", "").strip()
        date_str = entry.get("creationDate", "")

        # Format date
        try:
            # Example format: 2023-10-05T14:30:00Z
            date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")

            # Attach the UTC timezone because it ends with a 'Z'
            date = date.replace(tzinfo=pytz.UTC)

            # Get the entry's timezone if available
            timeZone = entry.get("timeZone")
            local_timezone = pytz.timezone(timeZone) if timeZone else pytz.UTC

            # Convert to local timezone
            local_date = date.astimezone(local_timezone)
            # Append this on the dates[] list
            dates.append(local_date)

            # Format the local time
            date_fmt = local_date.strftime("%d %b %Y %I:%M %p")

        except Exception:
            date_fmt = date_str

        # Convert entire entry Markdown → HTML
        normalized = normalize_list_boundaries(text)
        text_html = markdown.markdown(normalized, extensions=["extra", "sane_lists"])


        # Use first line as preview in TOC
        preview = text.splitlines()[0] if text else f"Entry {i}"
        # Remove leading Markdown heading markers (# plus spaces)
        preview = re.sub(r'^#+\s*', '', preview)
        toc_html += f'<li class="list-group-item d-flex justify-content-between align-items-center"><a href="#entry{i}">{date_fmt} — {preview}</a></li>\n'

        # Build location hyperlink if data exists
        location_html = ""
        loc = entry.get("location", {})
        lat = loc.get("latitude")
        lng = loc.get("longitude")
        place = loc.get("placeName", "")
        locality = loc.get("localityName", "")
        country = loc.get("country", "")

        if lat and lng:
            # Build display text (skip empty parts)
            location_text = ", ".join([x for x in [place, locality, country] if x])
            maps_url = f"https://www.google.com/maps?q={lat},{lng}"
            location_html = (
                f'<p class="muted-text">'
                f'<p><i class="bi bi-geo-alt-fill text-danger"></i> '
                f'<a href="{maps_url}" target="_blank">{location_text}</a></p>'
            )
        # Add weather information if available
        weather_info = entry.get('weather', {})
        wx_temp = weather_info.get('temperatureCelsius')
        wx_description = weather_info.get('conditionsDescription')

        if wx_temp is not None and wx_description:
            wx_line = f"{wx_temp:.1f}°C, {wx_description}"
        elif wx_temp is not None:
            wx_line = f"{wx_temp:.1f}°C"
        elif wx_description:
            wx_line = wx_description
        else:
            wx_line = ""

        # Embed photos and videos together in a Bootstrap grid
        media_html = []
        mime_map = {
            ".mp4": "video/mp4",
            # This somehow works to ensure that the MOV files play in the browser
            ".mov": "video/mp4",
            ".webm": "video/webm"
        }

        # Photos
        for photo in entry.get("photos", []):
            filename = photo.get("md5") or photo.get("identifier")
            if filename:
                for ext in [".jpg", ".jpeg", ".png"]:
                    path = os.path.join(photos_dir, filename + ext)
                    if os.path.exists(path):
                        # This converts the Python path to a browser-friendly one
                        url = f"file:///{os.path.abspath(path).replace(os.sep, '/')}"
                        safe_url = url.replace("'", "\\'")
                        media_html.append(
                            f'''
                            <div class="col-md-4">
                            <img src="{url}" class="img-fluid rounded mb-3"
                                alt="Photo"
                                data-bs-toggle="modal"
                                data-bs-target="#photoModal"
                                onclick="document.getElementById('modalImage').src='{safe_url}'">
                            </div>
                            '''
                        )
                        break

        # Videos
        for video in entry.get("videos", []):
            filename = video.get("md5") or video.get("identifier")
            if filename:
                for ext, mime in mime_map.items():
                    path = os.path.join(videos_dir, filename + ext)
                    if os.path.exists(path):
                        media_html.append(
                            f'<div class="col-md-6"><video controls class="w-100 mb-3">'
                            f'<source src="{path}" type="{mime}">'
                            'Your browser does not support the video tag.</video></div>'
                        )
                        break
        # Audio
        for audio in entry.get("audios", []):
            filename = audio.get("md5") or audio.get("identifier")
            if filename:
                path = os.path.join(audio_dir, filename + ".m4a")
                if os.path.exists(path):
                    media_html.append(
                        f'<div class="col-md-6"><audio controls class="w-100 mb-3">'
                        f'<source src="{path}" type="audio/mp4">'
                        'Your browser does not support the audio element.</audio></div>'
                    )

        # Wrap all media in a row
        media_block = ""
        if media_html:
            media_block = '<div class="row">' + "".join(media_html) + '</div>'

        # Build entry block using Bootstrap card
        entries_html += f"""
        <div class="card mb-4" id="entry{i}">
            <div class="card-body">
                <p class="text-muted">{date_fmt}</p>
                {location_html}
                <p class="text-muted">{wx_line}</p>
                <div class="card-text">{text_html}</div>
                {media_block}
                <a href="#toc" class="btn btn-link">Back to top</a>
            </div>
        </div>
        """
    # Find the earliest and latest dates
    if dates:
        start_date = min(dates)
        end_date = max(dates)
    date_range_str = f"from {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}" if dates else "No date information"

    # Wrap in full HTML with Bootstrap
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Journal entries</title>
        <!-- Bootstrap CSS -->
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" rel="stylesheet">
        <style>
            /* Font settings */
            p {{
                font-family: Roboto, sans-serif;
            }}

            h1, h2, {{
                font-family: 'Roboto Slab', serif;
            }}
            
            /* Indentation and bullets/numbers */
            .card-text ul,
            .card-text ol {{
                margin: 0.5rem 0 1rem;
                padding-left: 1.25rem;  /* indent */
            }}
            .card-text ul {{ list-style-type: disc; }}
            .card-text ol {{ list-style-type: decimal; }}
            .card-text li {{ margin-bottom: 0.25rem; }}

            /* Add hover effects */
            a {{
                color: #3d6eb7;
                text-decoration: none;
            }}
            .list-group-item a {{
                transition: color 0.2s ease;
                }}
            .list-group-item a:hover {{
                color: #0d6efd;
                font-weight: 500;
                }}
        </style>
    </head>
    <body class="bg-light">
        <div class="container my-5">
            <div class="row">
                <div class="col-lg-8 mx-auto">
                    <h1 class="text-center mb-4">Entries {date_range_str}</h1>
                    <div id="toc" class="mb-4">
                        <h2>Table of Contents</h2>
                        <ul class="list-group list-group-flush">
                            {toc_html}
                        </ul>
                    </div>
                    {entries_html}
                </div>
            </div>
        </div>
        <div class="modal fade" id="photoModal" tabindex="-1" aria-hidden="true">
            <div class="modal-dialog modal-dialog-centered modal-lg">
                <div class="modal-content bg-dark">
                    <div class="modal-header border-0">
                        <button type="button" class="btn-close btn-close-white"
                            data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body text-center">
                        <img id="modalImage" src="" alt="Enlarged photo" class="img-fluid">
                    </div>
                </div>
            </div>
        </div>
        <!-- Bootstrap JS (optional, for interactive components) -->
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """

    # Save single HTML file
    with open(output_file, "w", encoding="utf-8") as f_out:
        f_out.write(html_content)

    print(f"Journal exported to {output_file}")

# Example usage:
# convert_dayone_json_to_single_html("journal.json", photos_dir="path_to_photos", videos_dir="path_to_videos" , audio_dir="path_to_audios")
