Agricultural Sun and Water Metric Python Script

Summary:

The Agricultural Sun and Water Metrics python script is designed to take the percentage of shade values from calculations that were derived by Louis Wood specifically for the RUTE Suntracker and apply them to evapotranspiration raster data from OpenET. Standard evapotranspiration formulas were used to combine these two sets of data and return an adjusted evapotranspiration value for each year. 

Constraints:

This model assumes that ET changes linearly with shade due to the solar radiance value being the predominant moving variable within the ET formulas. It also does not account for light bouncing off the surroundings or any shade which would have been in the field previously. IT also makes significant simplifications assuming solar radiance is the predominant and only variable changing by adding solar panels to fields. As such, due to the simplifications made in creating this model, it should be accurate to one significant figure. This has been confirmed by Chad Higgins at Oregon State University.

Ideas for the Future:

This script could be modified to use precipitation data to add another level of usefulness. The OpenET dataset includes what type of crops are being grown in each field, and thus it could be determined by using additional precipitation data from OpenET if adding panels above any given agricultural land would allow the area to grow crops without irrigation. If the crop water requirement is less than the difference of the precipitation minus the adjusted ET, then that land would allow for sustainable nonirrigated growth.

How to use the script:

1.	Install Python
2.	Install required libraries
a.	Example: pip install skyfield
3.	Using any IDE, launch the python application
4.	Run the python application in the IDE
5.	Answer the questions in the command prompt
6.	Save water!
