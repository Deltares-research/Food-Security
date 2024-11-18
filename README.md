# Food-Security

## Data formatting

### Food production data

#### Other crops
Other crops data is expected to be in csv file format with production values per province. The production values is expected to be in thousand of tons per year. The column name of the production value should be the name of the file as is described in the config toml. For example, maize = "path/to/file.csv", here the column name should be maize. Also note that the column that is used to join the data to the main region dataframe can be named in the config toml. This column name should be the same among all other crop files.

