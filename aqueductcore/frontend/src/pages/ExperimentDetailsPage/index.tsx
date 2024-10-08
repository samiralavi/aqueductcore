import { useParams } from "react-router-dom";
import { Box, styled } from "@mui/material";

import { useGetExperimentById } from "API/graphql/queries/experiment/getExperimentById";
import { drawerTopOffset, mainPadding } from "components/templates/drawerLayout";
import ExperimentDetails from "components/organisms/ExperimentDetails";
import { FileSelectProvider } from "context/FileSelectProvider";
import Attachments from "components/organisms/Attachments";
import { Loading } from "components/atoms/Loading";
import { Error } from "components/atoms/Error";

const Container = styled(Box)`
  margin: -${mainPadding}px;
  margin-top: -${drawerTopOffset + mainPadding}px;
  padding: ${(props) => `${props.theme.spacing(2.5)}`};
`;

function ExperimentDetailsPage() {
  const { experimentIdentifier } = useParams();

  const {
    loading,
    data: experimentData,
    error,
  } = useGetExperimentById({
    variables: {
      experimentIdentifier: {
        type: experimentIdentifier?.split("-").length === 2 ? "EID" : "UUID",
        value: experimentIdentifier,
      },
    },
  });

  const experimentDetails = experimentData?.experiment;

  if (loading) return <Loading />;
  if (error) return <Error message={error.message} />;
  if (!experimentDetails) return <></>;

  return (
    <Container>
      <FileSelectProvider>
        <ExperimentDetails experimentDetails={experimentDetails} />
        <Attachments experimentUuid={experimentDetails.uuid} experimentFiles={experimentDetails.files} />
      </FileSelectProvider>
    </Container>
  );
}

export default ExperimentDetailsPage;
