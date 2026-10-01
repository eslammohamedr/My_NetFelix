#!/usr/bin/env python3
"""
Sync folders in /media/dell/Data1/Recovered/photos to Immich Albums
"""
import subprocess
import sys

SQL = """
DO $$
DECLARE
    v_user_id uuid := 'ea3baba4-cd96-4ff1-8fd9-9855321fcb71';
    rec RECORD;
    v_album_id uuid;
    v_thumb_id uuid;
BEGIN
    FOR rec IN 
        SELECT 
            split_part(replace("originalPath", '/media/dell/Data1/Recovered/photos/', ''), '/', 1) AS folder_name
        FROM asset 
        WHERE "originalPath" LIKE '/media/dell/Data1/Recovered/photos/%/%'
        GROUP BY folder_name
        ORDER BY folder_name
    LOOP
        SELECT id INTO v_album_id FROM album WHERE "albumName" = rec.folder_name LIMIT 1;
        
        IF v_album_id IS NULL THEN
            SELECT id INTO v_thumb_id 
            FROM asset 
            WHERE "originalPath" LIKE '/media/dell/Data1/Recovered/photos/' || rec.folder_name || '/%'
            LIMIT 1;

            INSERT INTO album ("albumName", "albumThumbnailAssetId", "order")
            VALUES (rec.folder_name, v_thumb_id, 'desc')
            RETURNING id INTO v_album_id;

            INSERT INTO album_user ("albumId", "userId", "role")
            VALUES (v_album_id, v_user_id, 'owner')
            ON CONFLICT DO NOTHING;
        END IF;

        INSERT INTO album_asset ("albumId", "assetId")
        SELECT v_album_id, id 
        FROM asset 
        WHERE "originalPath" LIKE '/media/dell/Data1/Recovered/photos/' || rec.folder_name || '/%'
        ON CONFLICT DO NOTHING;
    END LOOP;

    SELECT id INTO v_album_id FROM album WHERE "albumName" = 'Camera & Recovered (Unsorted)' LIMIT 1;
    IF v_album_id IS NULL THEN
        SELECT id INTO v_thumb_id 
        FROM asset 
        WHERE "originalPath" NOT LIKE '/media/dell/Data1/Recovered/photos/%/%'
        LIMIT 1;

        INSERT INTO album ("albumName", "albumThumbnailAssetId", "order")
        VALUES ('Camera & Recovered (Unsorted)', v_thumb_id, 'desc')
        RETURNING id INTO v_album_id;

        INSERT INTO album_user ("albumId", "userId", "role")
        VALUES (v_album_id, v_user_id, 'owner')
        ON CONFLICT DO NOTHING;
    END IF;

    INSERT INTO album_asset ("albumId", "assetId")
    SELECT v_album_id, id 
    FROM asset 
    WHERE "originalPath" NOT LIKE '/media/dell/Data1/Recovered/photos/%/%'
    ON CONFLICT DO NOTHING;

END $$;
"""

def main():
    print("Syncing Immich albums with folders...")
    proc = subprocess.run(
        ["docker", "exec", "-i", "netfelix-immich-postgres", "psql", "-U", "postgres", "-d", "immich"],
        input=SQL,
        text=True,
        capture_output=True
    )
    if proc.returncode == 0:
        print("Albums successfully synchronized!")
    else:
        print(f"Error syncing albums: {proc.stderr}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
