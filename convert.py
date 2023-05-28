import os
import json
import shutil
import glob
import nrrd
import numpy as np
from PIL import Image
from tqdm import tqdm

SCALE          = 0.1
VOLPKG_DIR     = '../full-scrolls/Scroll1.volpkg'
VOLUME_ID      = '20230205180739'
SEGMENT_LIST   = [ '20230506133355' ]

TIF_DIR        = f'{VOLPKG_DIR}/volumes_small/{VOLUME_ID}/'
OBJ_DIR        = f'{VOLPKG_DIR}/paths/'

# SCALE          = 1.0
# VOLPKG_DIR     = './output/pseudo.volpkg'
# VOLUME_ID      = '20230527161628'
# SEGMENT_LIST   = [ '20230527164921' ]

# TIF_DIR        = f'{VOLPKG_DIR}/volumes/{VOLUME_ID}/'
# OBJ_DIR        = f'{VOLPKG_DIR}/paths/'

NPZ_DIR        = './output/' + 'volume.npz'
NRRD_DIR       = './output/' + 'volume.nrrd'
META_DIR       = './output/' + 'meta.json'


if not os.path.exists('output'):
    os.makedirs('output')

def read_npz(NPZ_DIR, key):
    data = np.load(NPZ_DIR)
    array = np.array(data[key])

    return array

def write_npz(NPZ_DIR, TIF_DIR, data):
    c = data['boundingBox']['min'] * SCALE
    b = data['boundingBox']['max'] * SCALE

    c[c < 0] = 0
    b[b < 0] = 0

    clip = {}
    clip['x'] = int(c[0])
    clip['y'] = int(c[1])
    clip['z'] = int(c[2])
    clip['w'] = int(b[0] - c[0])
    clip['h'] = int(b[1] - c[1])
    clip['d'] = int(b[2] - c[2])

    # clip = { 'x': 0, 'y': 0, 'z': 0, 'w': 500, 'h': 250, 'd': 100 }
    print('clip: ', clip)

    names = sorted(glob.glob(TIF_DIR + '*tif'))
    names = names[clip['z'] : clip['z'] + clip['d']]
    image_stack = np.zeros((clip['w'], clip['h'], len(names)), dtype=np.float32)

    for i, filename in enumerate(tqdm(names)):
        image = np.array(Image.open(filename), dtype=np.float32)[clip['y']:(clip['y']+clip['h']), clip['x']:(clip['x']+clip['w'])]
        image /= 65535.0
        image_stack[:, :, i] = np.transpose(image, (1, 0))

    np.savez(NPZ_DIR, image_stack=image_stack)

    meta = {}
    meta['scale'] = SCALE
    meta['clip'] = clip
    meta['nrrd'] = 'volume.nrrd'
    meta['obj'] = SEGMENT_LIST

    with open(META_DIR, "w") as outfile:
        json.dump(meta, outfile)

def read_nrrd(NRRD_DIR):
    data, header = nrrd.read(NRRD_DIR)

def write_nrrd(NRRD_DIR, data):
    # header = {'spacings': [1.0, 1.0, 1.0]}
    # nrrd.write(NRRD_DIR, data, header)
    nrrd.write(NRRD_DIR, data)

def parse_obj(filename):
    vertices = []
    normals = []
    uvs = []
    faces = []

    with open(filename, 'r') as f:
        for line in f:
            if line.startswith('v '):
                vertices.append([float(x) for x in line[2:].split()])
            elif line.startswith('vn '):
                normals.append([float(x) for x in line[3:].split()])
            elif line.startswith('vt '):
                uvs.append([float(x) for x in line[3:].split()])
            elif line.startswith('f '):
                indices = [int(x.split('/')[0]) - 1 for x in line.split()[1:]]
                faces.append(indices)

    data = {}
    data['vertices']    = np.array(vertices)
    data['normals']     = np.array(normals)
    data['uvs']         = np.array(uvs)
    data['faces']       = np.array(faces)

    return data

def save_obj(filename, data):
    vertices = data['vertices']
    normals  = data['normals']
    uvs      = data['uvs']
    faces    = data['faces']

    with open(filename, 'w') as f:

        for i in range(len(vertices)):
            vertex = vertices[i]
            normal = normals[i]
            f.write(f"v {' '.join(str(x) for x in vertex)}\n")
            f.write(f"vn {' '.join(str(x) for x in normal)}\n")

        for uv in uvs:
            f.write(f"vt {' '.join(str(x) for x in uv)}\n")

        for face in faces:
            indices = ' '.join(f"{x+1}/{x+1}/{x+1}" for x in face)
            f.write(f"f {indices}\n")

def processing(data):
    vertices = data['vertices']
    normals  = data['normals']
    uvs      = data['uvs']
    faces    = data['faces']

    # calculate bounding box
    mean_vertices = np.mean(vertices, axis=0)
    max_x = np.max(np.abs(vertices[:, 0] - mean_vertices[0]))
    max_y = np.max(np.abs(vertices[:, 1] - mean_vertices[1]))
    max_z = np.max(np.abs(vertices[:, 2] - mean_vertices[2]))

    bounding_box = {}
    bounding_box['min'] = mean_vertices - np.array([max_x, max_y, max_z])
    bounding_box['max'] = mean_vertices + np.array([max_x, max_y, max_z])

    # translate & rescale
    p_vertices = vertices
    p_normals = normals
    p_uvs = uvs
    p_faces = faces

    p_data = {}
    p_data['vertices']    = p_vertices
    p_data['normals']     = p_normals
    p_data['uvs']         = p_uvs
    p_data['faces']       = p_faces
    p_data['boundingBox'] = bounding_box

    return p_data

# Read .obj file
data = parse_obj(f'{OBJ_DIR}{SEGMENT_LIST[0]}/{SEGMENT_LIST[0]}.obj')
# Processing .obj data
p_data = processing(data)
# Generate .npz file from .tif files
write_npz(NPZ_DIR, TIF_DIR, p_data)
# Generate .nrrd file from .npz file
write_nrrd(NRRD_DIR, read_npz(NPZ_DIR, 'image_stack'))

# Copy the generated files to the client folder
shutil.copy(NRRD_DIR , 'client/public')
shutil.copy(META_DIR , 'client/src')

for SEGMENT_ID in SEGMENT_LIST:
    filename = f'{OBJ_DIR}{SEGMENT_ID}/{SEGMENT_ID}.obj'
    shutil.copy(filename, 'output')
    shutil.copy(filename, 'client/public')



