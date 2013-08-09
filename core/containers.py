'''
Created on Jun 14, 2013

@author: jonathanfriedman

TODO:
'''
from FlowCytometryTools import parse_fcs
from bases import Measurement, MeasurementCollection, OrderedCollection
from GoreUtilities.util import to_list
from itertools import cycle
import graph


class FCMeasurement(Measurement):
    '''
    A class for holding flow cytometry data from
    a single well or a single tube.
    '''

    @property
    def channels(self):
        '''
        Channel information organized as a DataFrame
        '''
        if self.meta is not None:
            return self.meta['_channels_']
        
    @property
    def channel_names(self):
        '''
        A tuple containing the channel names
        '''
        if self.meta is not None:
            return self.meta['_channel_names_']

    def read_data(self, **kwargs):
        '''
        Read the datafile specified in Sample.datafile and
        return the resulting object.
        Does NOT assign the data to self.data
        '''
        meta, data = parse_fcs(self.datafile, **kwargs)
        return data

    def read_meta(self, **kwargs):
        '''
        '''
        kwargs['meta_data_only'] = True
        kwargs['reformat_meta'] = True
        meta = parse_fcs(self.datafile, **kwargs)
        return meta

    def get_meta_fields(self, fields, kwargs={}):
        '''
        TODO: change to extract data from other metadata fields (not just 'text')
        '''
#         if self.data is None:
#             raise Exception, 'Data must be read before extracting metadata.'
        fields = to_list(fields)
        func = lambda x: [x.get_meta()[field] for field in fields]
        kwargs.setdefault('applyto', 'sample')
        return self.apply(func, **kwargs)

    def ID_from_data(self, ID_field='$SRC'):
        '''
        Returns the well ID from the src keyword in the FCS file. (e.g., A2)
        This keyword may not appear in FCS files generated by other machines,
        in which case this function will raise an exception.
        '''
        try:
            return self.get_meta_fields(ID_field)[0]
        except:
            raise Exception("The keyword '{}' does not exist in the following FCS file: {}".format(ID_field, self.datafile))

    def plot(self, channel_names, kind='histogram', transform=(None, None), 
             gates=None, transform_first=True, apply_gates=True, plot_gates=True,
             gate_colors=None, **kwargs):
        '''
        Plots the flow cytometry data associated with the sample on the current axis.
        Follow with a call to matplotlibs show() in order to see the plot.

        Parameters
        ----------
        channel_names : str| iterable of str | None
            name (names) channels to plot.
            given a single channel plots a histogram
            given two channels produces a 2d plot
        kind : 'scatter', 'histogram'
        transform : valid transform | tuple of valid transforms | None
            Transform to be applied to corresponding channels using the FCMeasurement.transform function.
            If a single transform is given, it will be applied to all plotted channels.
        gates: Gate| iterable of Gate | None
            Gates to be applied before plotting
        transform_first : bool
            Apply transforms before gating.
        kwargs : dict
            Additional keyword arguments to be passed to graph.plotFCM

        Returns
        -------
        None: if no data is loaded
        gHandle: reference to axis


        TODO: fix default value of transform... need cycling function?
        '''
#         data = self.get_data() # The index is to keep only the data part (removing the meta data)
        # Transform sample

        def _trans(sample, channel_names, transformList):
            for c,t in zip(channel_names, transformList):
                if t is not None:
                    sample = sample.transform(t, channels=c)
                else:
                    pass
            return sample
        
        def _gates(sample, gates):
            if gates is None:
                return sample
            for gate in gates:
                sample = sample.gate(gate)
            return sample
        
        ax = kwargs.get('ax')
        
        channel_names = to_list(channel_names)
        transformList = to_list(transform)
        gates         = to_list(gates)
        
        if len(transformList)==1:
             transformList *= len(channel_names)
        
        sample_tmp = self.copy()
        if apply_gates:
            if transform_first:
                sample_tmp = _trans(sample_tmp, channel_names, transformList)
                sample_tmp = _gates(sample_tmp, gates)
            else:
                sample_tmp = _gates(sample_tmp, gates)
                sample_tmp = _trans(sample_tmp, channel_names, transformList)
        else:
            sample_tmp = _trans(sample_tmp, channel_names, transformList)
            
        data = sample_tmp.get_data()
        out  = graph.plotFCM(data, channel_names, kind=kind, **kwargs)
        
        #TODO: add gate color cycling
        if plot_gates and gates is not None:
            if gate_colors is None:
                gate_colors = cycle(('k', 'b', 'g', 'r', 'm', 'c', 'y'))
            for (g,c) in zip(gates, gate_colors):
                g.plot(ax=ax, ax_channels=channel_names, color=c)
        
        return out
        

    def view(self, channel_names=None):
        '''
        Loads the current FCS sample viewer

        Parameters
        ----------
        channel_names : str | list of str
            Names of channels to load by default

        Returns
        -------

        Output from sample_viewer
        '''
        from FlowCytometryTools import flowGUI
        return flowGUI.sample_viewer(self.datafile, channel_names=channel_names)

    def transform(self, transform, channels=None, direction='forward',  
                  return_all=True, args=(), **kwargs):
        '''
        Apply transform to specified channels. 
        Return a new sample with transformed data.
        '''
        from transforms import transform_frame
        data = self.get_data()
        newdata = transform_frame(data, transform, channels, direction,
                                           return_all, args, **kwargs)
        newsample = self.copy()
        newsample.set_data(data=newdata)
        return newsample
    
    def gate(self, gate):
        '''
        Apply given gate and return new gated sample (with assigned data).
        Note that no transformation is done by this funciton.
        '''
        data = self.get_data()
        newdata = gate(data)
        newsample = self.copy()
        newsample.set_data(data=newdata)
        return newsample        

class FCCollection(MeasurementCollection):
    '''
    A dict-like class for holding flow cytometry samples.
    '''
    _sample_class = FCMeasurement

class FCOrderedCollection(OrderedCollection, FCCollection):
    '''
    A dict-like class for holding flow cytometry samples that are arranged in a matrix.
    '''

    def plot(self, channel_names,  kind='histogram', transform=(None, None), 
             gates=None, transform_first=True, grid_plot_kwargs={},
             ids=None, row_labels=None, col_labels=None,
             xaxislim=None, yaxislim=None, **kwargs):
        """
        For details see documentation for FCMeasurement.plot
        Use grid_plot_kwargs to pass keyword arguments to the grid_plot function.
        (For options see grid_plot documentation)


        Returns
        -------
        gHandleList: list
            gHandleList[0] -> reference to main axis
            gHandleList[1] -> a list of lists
                example: gHandleList[1][0][2] returns the subplot in row 0 and column 2
        """
        def plotSampleDataFunction(sample, ax):
            """ Function assumes that data is returned as a 2-tuple. The first element is the meta data, the second is the DataFrame """
            return sample.plot(channel_names, transform=transform, ax=ax,
                               gates=gates, transform_first=transform_first,
                               kind=kind, autolabel=False, **kwargs)
        
        grid_plot_kwargs['ids'] = ids
        grid_plot_kwargs['row_labels'] = row_labels
        grid_plot_kwargs['col_labels'] = col_labels
        grid_plot_kwargs['xaxislim'] = xaxislim
        grid_plot_kwargs['yaxislim'] = yaxislim
        return self.grid_plot(plotSampleDataFunction, **grid_plot_kwargs)

FCPlate = FCOrderedCollection

if __name__ == '__main__':
    import glob
    datadir = '../tests/data/Plate02/'
    fname = glob.glob(datadir + '*.fcs')[0]
    sample = FCMeasurement(1, datafile=fname)
    print sample.channels
    print sample.channel_names

#     print plate
    #print plate.wells 
    #print plate.well_IDS
    
    #plate.apply(lambda x:x.ID, 'ID', applyto='sample', well_ids=['A1','B1'])
    #plate.apply(lambda x:x.datafile, 'file', applyto='sample')
    #plate.apply(lambda x:x.shape[0], 'counts', keepdata=True)
    #plate.get_well_metadata(['date', 'etim'])
    #print plate.extracted['file'].values
    
#     plate.wells['1']['A'].get_metadata()
#     
#     well_ids = ['A2' , 'B3']
#     print plate.get_wells(well_ids)
#     
#     plate.clear_well_data()  
#     plate.clear_well_data(well_ids)             
            
        
