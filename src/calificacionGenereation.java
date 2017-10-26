import java.util.Scanner;





public class calificacionGenereation {

	public static void main(String[] args) {
		// TODO Auto-generated method stub
		
		Scanner sc = new Scanner(System.in);
		String sName;
		byte bScoreMc=0,bScorePer=0,bScoreRp=0,bScoreOf=0,bScoreCom=0,bScoreTe=0,bScoreGt=0,bScoreOd=0;
		double averageMenGen, averageMenJava, averageGeneral;
		int sumGen, sumJava;
		
		String color1="Red";
		String color2="Yellow";
		String color3="Green";
		String color4="Blue";
		
	
		
		
		
		System.out.println(" Welcome to Generation evaluation system\n");
		
		System.out.println("Please enter your name: \n");
		
		sName=sc.nextLine();
		
		
		
		while (bScoreMc<=0  || bScoreMc>4){
			System.out.println("Enter score for Mentalidad de Crecimiento ");
			bScoreMc=sc.nextByte();}
		while (bScorePer<=0  || bScorePer>4){
			System.out.println("Enter score for Persistencia");
			bScorePer=sc.nextByte();}
		while (bScoreRp<=0  || bScoreRp>4){
			System.out.println("Enter score for Responsabilidad personal");
			bScoreRp=sc.nextByte();}
		while (bScoreOf<=0  || bScoreOf>4){
			System.out.println("Enter score for Orientación al Futuro");
			bScoreOf=sc.nextByte();}
		while (bScoreCom<=0  || bScoreCom>4){
			System.out.println("Enter score for Comunicaión");
			bScoreCom=sc.nextByte();}
		while (bScoreTe<=0  || bScoreTe>4){
			System.out.println("Enter score for Trabajo en Equipo");
			bScoreTe=sc.nextByte();}
		while (bScoreGt<=0  || bScoreGt>4){
			System.out.println("Enter score for Gestión del Tiempo");
			bScoreGt=sc.nextByte();}
		while (bScoreOd<=0  || bScoreOd>4){
			System.out.println("Enter score for Orientacion al Detalle");
			bScoreOd=sc.nextByte();}
		
		System.out.println("Thanks, I will calculate your final score\n");
		System.out.println(sName+" your scores are: \n\n");
		
		sumGen=bScoreMc+bScorePer+bScoreRp+bScoreOf;
		sumJava=bScoreCom+bScoreTe+bScoreGt+bScoreOd;
		
		averageMenGen=sumGen;
		averageMenGen=averageMenGen/4;
		averageMenJava= sumGen;
		averageMenJava=averageMenJava/4;
		averageGeneral= sumGen+sumJava;
		averageGeneral= averageGeneral/8;
		
		System.out.println("               Mentalidades de Generation               \n");
		
		if ( bScoreMc==1) {
			System.out.println("Mentalidad de crecimiento "+bScoreMc+"     "+color1);
			}else if ( bScoreMc==2) {
			System.out.println("Mentalidad de crecimiento "+bScoreMc+"     "+color2);
			}else if ( bScoreMc==3) {
			System.out.println("Mentalidad de crecimiento "+bScoreMc+"     "+color3);
			}else if ( bScoreMc==4) {
			System.out.println("Mentalidad de crecimiento "+bScoreMc+"     "+color4);
			}
		
		

		if ( bScorePer==1) {
			System.out.println("Persistencia              "+bScorePer+"     "+color1);
			}else if ( bScorePer==2) {
			System.out.println("Persistencia              "+bScorePer+"     "+color2);
			}else if ( bScorePer==3) {
			System.out.println("Persistencia              "+bScorePer+"     "+color3);
			}else if ( bScorePer==4) {
			System.out.println("Persistencia              "+bScorePer+"     "+color4);
			}
		
		
		if ( bScoreRp==1) {
			System.out.println("Responsabilidad personal  "+bScoreRp+"     "+color1);
			}else if ( bScoreRp==2) {
			System.out.println("Responsabilidad personal  "+bScoreRp+"     "+color2);
			}else if ( bScoreRp==3) {
			System.out.println("Responsabilidad personal  "+bScoreRp+"     "+color3);
			}else if ( bScoreRp==4) {
			System.out.println("Responsabilidad personal  "+bScoreRp+"     "+color4);
			}
		
		if ( bScoreOf==1) {
			System.out.println("Orientación al futuro     "+bScoreOf+"     "+color1);
			}else if ( bScoreOf==2) {
			System.out.println("Orientación al futuro     "+bScoreOf+"     "+color2);
			}else if ( bScoreOf==3) {
			System.out.println("Orientación al futuro     "+bScoreOf+"     "+color3);
			}else if ( bScoreOf==4) {
			System.out.println("Orientación al futuro     "+bScoreOf+"     "+color4);
			}
		
		System.out.println("\n"+"               Mentalidades de Java               \n");
		
		if ( bScoreCom==1) {
			System.out.println("Comunicación              "+bScoreCom+"     "+color1);
			}else if ( bScoreCom==2) {
			System.out.println("Comunicación              "+bScoreCom+"     "+color2);
			}else if ( bScoreCom==3) {
			System.out.println("Comunicación              "+bScoreCom+"     "+color3);
			}else if ( bScoreCom==4) {
			System.out.println("Comunicación              "+bScoreCom+"     "+color4);
			}
		
		if ( bScoreTe==1) {
			System.out.println("Trabajo en equipo         "+bScoreTe+"     "+color1);
			}else if ( bScoreTe==2) {
			System.out.println("Trabajo en equipo         "+bScoreTe+"     "+color2);
			}else if ( bScoreTe==3) {
			System.out.println("Trabajo en equipo         "+bScoreTe+"     "+color3);
			}else if ( bScoreTe==4) {
			System.out.println("Trabajo en equipo         "+bScoreTe+"     "+color4);
			}
		
		if ( bScoreGt==1) {
			System.out.println("Gestion del tiempo        "+bScoreGt+"     "+color1);
			}else if ( bScoreGt==2) {
			System.out.println("Gestion del tiempo        "+bScoreGt+"     "+color2);
			}else if ( bScoreGt==3) {
			System.out.println("Gestion del tiempo    	  "+bScoreGt+"     "+color3);
			}else if ( bScoreGt==4) {
			System.out.println("Gestion del tiempo        "+bScoreGt+"     "+color4);
			}
		if ( bScoreOd==1) {
			System.out.println("Orientacion al detalle    "+bScoreOd+"     "+color1);
			}else if ( bScoreOd==2) {
			System.out.println("Orientacion al detalle    "+bScoreOd+"     "+color2);
			}else if ( bScoreOd==3) {
			System.out.println("Orientacion al detalle    "+bScoreOd+"     "+color3);
			}else if ( bScoreOd==4) {
			System.out.println("Orientacion al detalle    "+bScoreOd+"     "+color4);
			}
		
		
		System.out.println("\n"+"Sum of Generation mentalities scores is: "+sumGen+"\n");
				
		System.out.println("Sum of Java mentalities scores is:       "+sumJava+"\n");
		
		System.out.println("Average of Generation mentalities is:    "+averageMenGen+"\n");
		
		System.out.println("Average of Java mentalities scores is:   "+averageMenJava+"\n");
		
		System.out.println("The average of all your scores is        "+averageGeneral+"\n");
		
		
		
		

	}

}
