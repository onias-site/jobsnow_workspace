import java.io.FileOutputStream;
import java.net.InetAddress;
import java.net.Socket;

import org.jacoco.core.data.ExecutionDataWriter;
import org.jacoco.core.runtime.RemoteControlReader;
import org.jacoco.core.runtime.RemoteControlWriter;

/**
 * Asks a JaCoCo agent started with output=tcpserver for its execution data and writes it to a .exec file,
 * the same thing "jacococli dump" does. Used for the API process, which is stopped by force afterwards and so
 * never gets to write the data on exit.
 *
 * usage: AgentDump <port> <output.exec>
 */
public class AgentDump {

	public static void main(String[] args) throws Exception {
		int port = Integer.parseInt(args[0]);
		try (FileOutputStream output = new FileOutputStream(args[1]);
				Socket socket = new Socket(InetAddress.getLoopbackAddress(), port)) {
			ExecutionDataWriter fileWriter = new ExecutionDataWriter(output);
			RemoteControlWriter remoteWriter = new RemoteControlWriter(socket.getOutputStream());
			RemoteControlReader remoteReader = new RemoteControlReader(socket.getInputStream());
			remoteReader.setSessionInfoVisitor(fileWriter);
			remoteReader.setExecutionDataVisitor(fileWriter);
			remoteWriter.visitDumpCommand(true, false);
			if (!remoteReader.read()) {
				throw new IllegalStateException("The agent closed the connection before sending the data");
			}
		}
	}
}
