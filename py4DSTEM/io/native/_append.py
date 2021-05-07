# Append additional DataObjects to an existing py4DSTEM formatted .h5 file.
# 
# See filestructure.txt for a description of the file structure.

import h5py
import numpy as np
from .read_utils import is_py4DSTEM_file
from .read_utils import get_N_dataobjects, get_py4DSTEM_topgroups
from .write import save_datacube_group, save_diffraction_group, save_real_group
from .write import save_pointlist_group, save_pointlistarray_group
from .write import save_counted_datacube_group
from .metadata import metadata_to_h5
from ..datastructure import DataObject,Metadata,DataCube

def _append(filepath, data, overwrite=0, topgroup='4DSTEM_experiment'):
    """
    Internal append function to avoid circular imports.  See io.append for docstring.
    """
    assert overwrite in (0,1,2), "'overwrite' must have a value of 0,1 or 2."
    # Construct dataobject list
    if isinstance(data, DataObject):
        dataobject_list = [data]
    elif isinstance(data, list):
        assert all([isinstance(item,DataObject) for item in data]), "If 'data' is a list, all items must be DataObjects."
        dataobject_list = data
    else:
        raise TypeError("Error: unrecognized value for argument data. Must be a DataObject or list of DataObjects")
    tgs = get_py4DSTEM_topgroups(filepath)
    if len(tgs)>1:
        assert(overwrite!=2), "`Hard` overwriting objects is not supported in multi-topgroup files"
    if topgroup not in tgs:
        print("This py4DSTEM file contains the following topgroups -- please specify one:")
        print("")
        for tg in tgs:
            print(tg)
        return

    # Read the file
    assert(is_py4DSTEM_file(filepath)), "Error: file is not recognized as a py4DSTEM file."
    N_dc,N_cdc,N_ds,N_rs,N_pl,N_pla,N_do = get_N_dataobjects(filepath,topgroup=topgroup)
    with h5py.File(filepath,"r+") as f:
        # Get data groups
        group_data = f[topgroup]['data']
        grp_dc = f[topgroup]['data/datacubes']
        grp_cdc = f[topgroup]['data/counted_datacubes']
        grp_ds = f[topgroup]['data/diffractionslices']
        grp_rs = f[topgroup]['data/realslices']
        grp_pl = f[topgroup]['data/pointlists']
        grp_pla = f[topgroup]['data/pointlistarrays']
        grp_md = f[topgroup]['metadata']

        # Identify metadata, either passed as arguments or attached to DataCubes
        metadata_list = [isinstance(dataobject_list[i],Metadata) for i in range(len(dataobject_list))]
        for dataobject in dataobject_list:
            if isinstance(dataobject,DataCube):
                if hasattr(dataobject,'metadata'):
                    metadata_list.append(dataobject.metadata)
        assert np.sum(metadata_list)<2, "Multiple Metadata instances were passed"
        try:
            i = metadata_list.index(True)
            md = dataobject_list.pop(i)
        except ValueError:
            md = None

        # Loop through and save all objects in the dataobjectlist
        names,grps,save_fns = [],[],[]
        lookupTable = {
                'DataCube':['datacube_',N_dc,grp_dc,
                                   save_datacube_group],
                'CountedDataCube':['counted_data_cube_',N_cdc,grp_cdc,
                                             save_counted_datacube_group],
                'DiffractionSlice':['diffractionslice_',N_ds,grp_ds,
                                                save_diffraction_group],
                'RealSlice':['realslice_',N_rs,grp_rs,
                                         save_real_group],
                'PointList':['pointlist_',N_pl,grp_pl,
                                    save_pointlist_group],
                'PointListArray':['pointlistarray_',N_pla,grp_pla,
                                           save_pointlistarray_group],
                 }
        for dataobject in dataobject_list:
            name = dataobject.name
            dtype = type(dataobject).__name__
            basename,N,grp,save_fn = lookupTable[dtype]
            if name == '':
                name = basename+str(N)
                N += 1
            names.append(name)
            grps.append(grp)
            # Check for overwrite conflicts
            if name in grp.keys():
                if overwrite==0:
                    save_fn = False
                else:
                    del grp[name]
            save_fns.append(save_fn)

        # Error message if there are overwrite conflicts
        if not all(save_fns):
            inds = np.nonzero([i==False for i in save_fns])[0]
            dtypes,names = [],[]
            for i in inds:
                dtypes.append(type(dataobject_list[i]).__name__)
                names.append(dataobject_list[i].name)
            print('While attempting to append data, one or more DataObjects were found with types/names which already exist in this h5 file. Conflicts were found with the following objects:')
            print('')
            for dtype,name in zip(dtypes,names):
                print("{} '{}'".format(dtype,name))
            print('')
            print("Either rename these objects before saving, or pass `overwrite=1` or `overwrite=2`. See the docstring for more info.")
            print("No objects saved.")
            return

        # Save objects
        else:
            # Save metadata
            if md is not None:
                metadata_to_h5(filepath,md,overwrite=overwrite,topgroup=topgroup)
            # Save data
            for name,grp,save_fn,do in zip(names,grps,save_fns,dataobject_list):
                new_grp = grp.create_group(name)
                print("Saving {} '{}'...".format(type(do).__name__,name))
                save_fn(new_grp,do)
        f.close()


